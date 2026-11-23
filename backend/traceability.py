"""Immutable requirement versions and release evidence, using existing evaluation results."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
import html
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import Session, PolicyVersion, RequirementVersion, RunRequirement, Run, Case, Dataset, CaseSource, Release, Review, ReleaseExport
from .specs import fingerprint

router = APIRouter()
STATE_LABELS = {'passed':'통과','failed':'실패','unverified':'미검증','unevaluable':'평가 불가'}

def now():
    return datetime.now(timezone.utc).isoformat()

class Ref(BaseModel):
    model_config = ConfigDict(extra='forbid')
    identifier: str = Field(pattern=r'^REQ-[A-Z0-9-]+$', max_length=100)
    version: int = Field(ge=1)

class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refund_min_recall: float = Field(ge=0,le=1)
    refund_max_drop: float = Field(ge=0,le=1)

class PolicyInput(BaseModel):
    identifier: str = Field(pattern=r'^POL-[A-Z0-9-]+$',max_length=100)
    version: int = Field(ge=1)
    config: PolicyConfig

class RequirementInput(Ref):
    title: str = Field(min_length=1,max_length=200)
    verification_condition: str = Field(min_length=1,max_length=2000)
    owner: str = Field(min_length=1,max_length=100)
    status: Literal['draft','active','retired'] = 'active'
    mandatory: bool = True
    policy_identifier: str
    policy_version: int = Field(ge=1)

def requirement_snapshot(s, item):
    policy = s.get(PolicyVersion,item.policy_id)
    return {'id':item.id,'identifier':item.identifier,'version':item.version,'title':item.title,
            'verification_condition':item.verification_condition,'owner':item.owner,'status':item.status,
            'mandatory':item.mandatory,'policy':{'identifier':policy.identifier,'version':policy.version,'config':policy.config}}

def resolve_requirements(s, refs):
    output=[]
    identities=set()
    for ref in sorted(refs,key=lambda r:(r.identifier,r.version)):
        if ref.identifier in identities:
            raise HTTPException(422,'한 실행/릴리스에는 요구사항 ID별 한 버전만 적용할 수 있습니다')
        identities.add(ref.identifier)
        item=s.scalar(select(RequirementVersion).where(RequirementVersion.identifier==ref.identifier,RequirementVersion.version==ref.version))
        if not item:
            raise HTTPException(404,f'요구사항 없음: {ref.identifier} v{ref.version}')
        output.append(requirement_snapshot(s,item))
    return output

def combined_policy(requirements, fallback):
    if not requirements:
        return fallback
    configs=[r['policy']['config'] for r in requirements]
    return {'refund_min_recall':max(p['refund_min_recall'] for p in configs),
            'refund_max_drop':min(p['refund_max_drop'] for p in configs)}

def requirement_verdict(rows, requirement):
    # Reuse the original numeric gate, including the no-refund-samples rule.
    from .evaluation import compare
    gate=compare(rows,requirement['policy']['config'])
    status='unevaluable' if not gate['refund_evaluable'] else ('passed' if gate['recommendation']=='approve' else 'failed')
    b,c=gate['baseline']['classes']['환불'],gate['candidate']['classes']['환불']
    return {'status':status,'status_label':STATE_LABELS[status],'reasons':gate['reasons'],
            'observed':{'baseline_refund_recall':b['recall'],'candidate_refund_recall':c['recall'],
                        'refund_drop':None if c['recall'] is None else b['recall']-c['recall'],'refund_support':c['support']},
            'violation_case_ids':[r['case_id'] for r in rows if r['expected_label']=='환불' and r['candidate']!='환불']}

@router.post('/policies',status_code=201)
def create_policy(body:PolicyInput):
    with Session() as s:
        old=s.scalar(select(PolicyVersion).where(PolicyVersion.identifier==body.identifier,PolicyVersion.version==body.version))
        if old:
            if old.config!=body.config.model_dump():
                raise HTTPException(409,'이미 존재하는 정책 버전은 수정할 수 없습니다. 새 버전을 등록하세요')
            return {'id':old.id,**body.model_dump()}
        item=PolicyVersion(identifier=body.identifier,version=body.version,config=body.config.model_dump())
        s.add(item)
        try:s.commit()
        except IntegrityError:
            s.rollback();return create_policy(body)
        return {'id':item.id,**body.model_dump()}

@router.post('/requirements',status_code=201)
def create_requirement(body:RequirementInput):
    if any(not x.strip() for x in [body.title,body.verification_condition,body.owner]):
        raise HTTPException(422,'제목·검증 조건·담당자는 공백일 수 없습니다')
    with Session() as s:
        policy=s.scalar(select(PolicyVersion).where(PolicyVersion.identifier==body.policy_identifier,PolicyVersion.version==body.policy_version))
        if not policy:raise HTTPException(404,'정책 버전 없음')
        values=body.model_dump(exclude={'policy_identifier','policy_version'})
        old=s.scalar(select(RequirementVersion).where(RequirementVersion.identifier==body.identifier,RequirementVersion.version==body.version))
        if old:
            if old.policy_id!=policy.id or any(getattr(old,k)!=v for k,v in values.items()):
                raise HTTPException(409,'요구사항 버전은 불변입니다. 새 버전을 등록하세요')
            return requirement_snapshot(s,old)
        item=RequirementVersion(**values,policy_id=policy.id);s.add(item)
        try:s.commit()
        except IntegrityError:
            s.rollback();return create_requirement(body)
        return requirement_snapshot(s,item)

@router.post('/requirements/sample',status_code=201)
def sample_requirement():
    create_policy(PolicyInput(identifier='POL-REFUND-001',version=1,config=PolicyConfig(refund_min_recall=.85,refund_max_drop=.05)))
    return create_requirement(RequirementInput(identifier='REQ-REFUND-001',version=1,title='환불 문의 품질 보존',
        verification_condition='후보 환불 재현율 85% 이상, 기준 대비 하락폭 5%p 이하',owner='AI 백엔드 담당자',
        policy_identifier='POL-REFUND-001',policy_version=1))

@router.get('/requirements')
def list_requirements():
    with Session() as s:
        return [requirement_snapshot(s,r) for r in s.scalars(select(RequirementVersion).order_by(RequirementVersion.identifier,RequirementVersion.version))]

@router.get('/requirements/{identifier}/versions/{version}')
def requirement_detail(identifier:str,version:int):
    with Session() as s:
        req=resolve_requirements(s,[Ref(identifier=identifier,version=version)])[0]
        evidence=[]
        for link in s.scalars(select(RunRequirement).where(RunRequirement.requirement_id==req['id']).order_by(RunRequirement.run_id)):
            run=s.get(Run,link.run_id)
            violation_ids=set((link.result or {}).get('violation_case_ids',[]))
            evidence.append({'run_id':run.id,'run_status':run.status,'mode_label':mode_label(run),
                'dataset_version':run.snapshot['dataset_version'],'requirement_snapshot':link.snapshot,
                'verdict':link.result or {'status':'unverified','status_label':'미검증'},
                'violation_cases':[r for r in (run.result or {}).get('cases',[]) if r['case_id'] in violation_ids],
                'regression_links':source_links(s,run.id)})
        return {'requirement':req,'status_label':'미검증' if not evidence else '실행별 판정 확인','evidence':evidence}

def mode_label(run):
    return '시나리오 데모' if run and run.snapshot['mode']=='scenario' else '실제 로컬 모델 평가'

def source_links(s,run_id):
    return [{'source_run_id':x.source_run_id,'source_case_id':x.source_case_id,'target_dataset_id':x.dataset_id,
             'target_dataset_version':s.get(Dataset,x.dataset_id).version,'target_case_id':s.get(Case,x.case_id).case_id}
            for x in s.scalars(select(CaseSource).where(CaseSource.source_run_id==run_id).order_by(CaseSource.id))]

class RegressionLinks(BaseModel):
    target_dataset_id:str
    case_ids:list[str]=Field(min_length=1,max_length=100)

@router.post('/runs/{run_id}/regression-links',status_code=201)
def link_regressions(run_id:str,body:RegressionLinks):
    from .analysis import regressions
    with Session() as s:
        run,target=s.get(Run,run_id),s.get(Dataset,body.target_dataset_id)
        if not run or not target:raise HTTPException(404,'실행/대상 테스트 세트 없음')
        if run.status!='succeeded':raise HTTPException(409,'완료된 실행만 연결할 수 있습니다')
        failures={c['case_id']:c for c in regressions(run)}
        if not set(body.case_ids)<=failures.keys():raise HTTPException(422,'기준만 정답인 회귀 사례만 연결할 수 있습니다')
        target_cases={(c.text.strip(),c.expected_label):c for c in s.scalars(select(Case).where(Case.dataset_id==target.id))}
        pending=[]
        for case_id in sorted(set(body.case_ids)):
            row=failures[case_id];case=target_cases.get((row['text'].strip(),row['expected_label']))
            if not case:raise HTTPException(409,'대상 세트에 없는 원문입니다. 기존 dataset-versions API로 새 세트를 만드세요')
            old=s.scalar(select(CaseSource).where(CaseSource.dataset_id==target.id,CaseSource.source_run_id==run_id,CaseSource.source_case_id==case_id))
            if not old:pending.append(CaseSource(dataset_id=target.id,case_id=case.id,source_run_id=run_id,source_case_id=case_id))
        s.add_all(pending)
        try:s.commit()
        except IntegrityError:
            s.rollback();return link_regressions(run_id,body)
        return {'added_cases':0,'created_links':len(pending),'target_dataset_version':target.version,'links':source_links(s,run_id)}

class SourceRef(BaseModel):
    source_run_id:str
    source_case_id:str

class ReleaseInput(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    initial_run_id:str|None=None
    candidate_run_id:str|None=None
    holdout_run_id:str|None=None
    requirements:list[Ref]=Field(min_length=1,max_length=30)
    reproduction_sources:list[SourceRef]=Field(default_factory=list,max_length=100)

def run_summary(run):
    if not run:return None
    return {'id':run.id,'status':run.status,'mode_label':mode_label(run),'snapshot':run.snapshot,'result':run.result}

def policy_identity(run):
    return {'config':run.snapshot['policy'],'versions':sorted(
        [(r['policy']['identifier'],r['policy']['version']) for r in run.snapshot.get('requirements',[])])}

def compare_runs(initial,candidate):
    reasons=[]
    if not initial or not candidate or initial.status!='succeeded' or candidate.status!='succeeded':
        reasons.append('두 실행이 모두 완료되어야 직접 비교할 수 있습니다')
    else:
        if initial.snapshot['dataset_version']!=candidate.snapshot['dataset_version']:
            reasons.append('테스트 세트 버전이 달라 직접 지표 비교를 제한합니다')
        if policy_identity(initial)!=policy_identity(candidate):
            reasons.append('정책 설정 또는 정책 버전이 달라 직접 지표 비교를 제한합니다')
        if initial.snapshot['mode']!=candidate.snapshot['mode']:
            reasons.append('시나리오 데모와 실제 모델 평가를 직접 비교할 수 없습니다')
        if initial.snapshot.get('effective_spec',{}).get('baseline_config')!=candidate.snapshot.get('effective_spec',{}).get('baseline_config'):
            reasons.append('기준 모델 설정이 다릅니다')
    deltas=None
    if not reasons:
        a,b=initial.result['candidate'],candidate.result['candidate']
        ar,br=a['classes']['환불']['recall'],b['classes']['환불']['recall']
        deltas={'accuracy':b['accuracy']-a['accuracy'],'refund_recall':None if ar is None or br is None else br-ar,
                'accuracy_improved':b['accuracy']>a['accuracy'],'refund_recall_improved':None if ar is None or br is None else br>ar}
    return {'allowed':not reasons,'restriction_reasons':reasons,'deltas':deltas}

def reproduction_results(s,release,candidate):
    from .evaluation import metrics
    rows=[];used=set()
    candidate_rows=(candidate.result or {}).get('cases',[]) if candidate else []
    by_content={(c['text'].strip(),c['expected_label']):c for c in candidate_rows}
    for source in release.reproduction_sources:
        original=s.get(Run,source['source_run_id'])
        row=next(c for c in original.result['cases'] if c['case_id']==source['source_case_id'])
        identity=(row['text'].strip(),row['expected_label']);used.add(identity)
        corrected=by_content.get(identity)
        rows.append({**source,'text':row['text'],'expected_label':row['expected_label'],'initial_prediction':row['candidate'],
                     'candidate_case_id':corrected['case_id'] if corrected else None,
                     'candidate_prediction':corrected['candidate'] if corrected else None,
                     'status':'unverified' if not corrected else ('passed' if corrected['candidate']==corrected['expected_label'] else 'failed'),
                     'target_dataset_version':candidate.snapshot['dataset_version'] if candidate else None})
    unused=[r for r in candidate_rows if (r['text'].strip(),r['expected_label']) not in used]
    metric=metrics([r['expected_label'] for r in unused],[r['candidate'] for r in unused]) if unused else None
    return {'used_cases':rows,'unused_subset':{'label':'수정에 사용하지 않은 사례 부분집합 · 독립 평가 세트 아님','count':len(unused),'metrics':metric}}

def requirement_states(s,release,candidate):
    output=[]
    for req in release.requirements:
        link=s.get(RunRequirement,(candidate.id,req['id'])) if candidate else None
        verdict=link.result if link and candidate.status=='succeeded' and link.result else {'status':'unverified','status_label':'미검증','reasons':['수정 후보에 연결된 완료 평가가 없습니다']}
        if req['status']!='active':
            verdict={'status':'unverified','status_label':'미검증','reasons':['활성 요구사항 버전이 아닙니다']}
        output.append({'requirement':req,'evidence_run_id':candidate.id if link else None,'verdict':verdict})
    return output

def holdout_summary(s,release,candidate):
    holdout=s.get(Run,release.holdout_run_id) if release.holdout_run_id else None
    reasons=[]
    if not candidate or candidate.status!='succeeded':
        return {'status':'unverified','label':'독립 평가 세트 미검증','reasons':['완료된 수정 후보와의 설정 일치를 확인할 수 없습니다'],'run':run_summary(holdout)}
    if not holdout or holdout.status!='succeeded':
        return {'status':'unverified','label':'독립 평가 세트 미검증','reasons':['별도 완료된 holdout_run_id가 없습니다'],'run':run_summary(holdout)}
    used_texts=set()
    for source in release.reproduction_sources:
        run=s.get(Run,source['source_run_id'])
        used_texts.add(next(c['text'].strip() for c in run.result['cases'] if c['case_id']==source['source_case_id']))
    if any(c['text'].strip() in used_texts for c in holdout.result['cases']):reasons.append('수정 사용 사례가 독립 세트에 포함되어 있습니다')
    if candidate:
        if holdout.snapshot['dataset_version']==candidate.snapshot['dataset_version']:reasons.append('별도 테스트 세트 버전이 아닙니다')
        for key in ['candidate_config','model_implementation','training_sha256','scenario_hash']:
            if holdout.snapshot.get('effective_spec',{}).get(key)!=candidate.snapshot.get('effective_spec',{}).get(key):reasons.append('후보 모델 유효 설정이 다릅니다');break
        if holdout.snapshot['commit_sha']!=candidate.snapshot['commit_sha']:reasons.append('후보 커밋이 다릅니다')
        if policy_identity(holdout)!=policy_identity(candidate):reasons.append('후보 정책이 다릅니다')
    return {'status':'unevaluable' if reasons else 'evaluated','label':'독립 평가 세트','reasons':reasons,'run':run_summary(holdout)}

def release_detail_in_session(s,release):
    initial=s.get(Run,release.initial_run_id) if release.initial_run_id else None
    candidate=s.get(Run,release.candidate_run_id) if release.candidate_run_id else None
    requirements=requirement_states(s,release,candidate)
    blockers=[f"{r['requirement']['identifier']} v{r['requirement']['version']}: {r['verdict']['status_label']}" for r in requirements if r['requirement']['mandatory'] and r['verdict']['status']!='passed']
    if not candidate or candidate.status!='succeeded':blockers.append('수정 후보 평가가 완료되지 않았습니다')
    history=[{'id':r.id,'run_id':r.run_id,'release_id':r.release_id,'reviewer':r.reviewer,'decision':r.decision,'reason':r.reason,'evidence':r.evidence,'created_at':r.created_at} for r in s.scalars(select(Review).where(Review.release_id==release.id).order_by(Review.id))]
    return {'id':release.id,'name':release.name,'created_at':release.created_at,'requirements':requirements,
            'initial_run':run_summary(initial),'candidate_run':run_summary(candidate),'comparison':compare_runs(initial,candidate),
            'reproduction':reproduction_results(s,release,candidate),'independent_evaluation':holdout_summary(s,release,candidate),
            'approval_allowed':not blockers,'approval_restrictions':blockers,'reviews':history,
            'regression_links':source_links(s,initial.id) if initial else [],
            'system_verdict':'passed' if not blockers else 'hold',
            'scenario_demo':any(r and r.snapshot['mode']=='scenario' for r in [initial,candidate])}

@router.post('/releases',status_code=201)
def create_release(body:ReleaseInput):
    with Session() as s:
        reqs=resolve_requirements(s,body.requirements)
        for run_id in [body.initial_run_id,body.candidate_run_id,body.holdout_run_id]:
            if run_id and not s.get(Run,run_id):raise HTTPException(404,'근거 실행 없음')
        sources=sorted({(x.source_run_id,x.source_case_id) for x in body.reproduction_sources})
        candidate=s.get(Run,body.candidate_run_id) if body.candidate_run_id else None
        for run_id,case_id in sources:
            source=s.get(Run,run_id)
            if not source or source.status!='succeeded' or run_id!=body.initial_run_id:
                raise HTTPException(422,'재현 출처는 완료된 최초 실패 실행이어야 합니다')
            from .analysis import regressions
            if case_id not in {c['case_id'] for c in regressions(source)}:raise HTTPException(422,'회귀 사례가 아닌 출처입니다')
            if candidate and not s.scalar(select(CaseSource.id).where(CaseSource.dataset_id==candidate.dataset_id,CaseSource.source_run_id==run_id,CaseSource.source_case_id==case_id)):
                raise HTTPException(422,'수정 후보 대상 세트에 회귀 출처를 먼저 연결하세요')
        release=Release(id=str(uuid4()),name=body.name,initial_run_id=body.initial_run_id,candidate_run_id=body.candidate_run_id,
            holdout_run_id=body.holdout_run_id,requirements=reqs,reproduction_sources=[{'source_run_id':a,'source_case_id':b} for a,b in sources],created_at=now())
        s.add(release);s.commit()
        return release_detail_in_session(s,release)

@router.get('/releases')
def list_releases():
    with Session() as s:
        return [{'id':r.id,'name':r.name,'created_at':r.created_at} for r in s.scalars(select(Release).order_by(Release.created_at.desc()))]

@router.get('/releases/{release_id}')
def get_release(release_id:str):
    with Session() as s:
        item=s.get(Release,release_id)
        if not item:raise HTTPException(404,'릴리스 검토 없음')
        return release_detail_in_session(s,item)

class ReleaseDecision(BaseModel):
    reviewer:str=Field(min_length=1,max_length=100)
    decision:Literal['approve','hold']
    reason:str=Field(min_length=1,max_length=4000)

@router.post('/releases/{release_id}/reviews',status_code=201)
def review_release(release_id:str,body:ReleaseDecision):
    if not body.reason.strip() or not body.reviewer.strip():raise HTTPException(422,'검토자·검토 사유를 입력하세요')
    with Session() as s:
        release=s.get(Release,release_id,with_for_update=True)
        if not release:raise HTTPException(404,'릴리스 검토 없음')
        detail=release_detail_in_session(s,release)
        if body.decision=='approve' and not detail['approval_allowed']:
            raise HTTPException(409,{'message':'필수 요구사항 미통과로 일반 승인을 제한합니다','restrictions':detail['approval_restrictions']})
        candidate=s.get(Run,release.candidate_run_id) if release.candidate_run_id else None
        if not candidate or candidate.status!='succeeded':raise HTTPException(409,'완료된 수정 후보가 있어야 검토를 기록할 수 있습니다')
        evidence={'initial_run_id':release.initial_run_id,'candidate_run_id':release.candidate_run_id,
                  'holdout_run_id':release.holdout_run_id,'requirements':detail['requirements'],'system_verdict':detail['system_verdict']}
        review=Review(run_id=candidate.id,release_id=release.id,evidence=evidence,**body.model_dump(),created_at=now())
        s.add(review);s.commit()
        return {'id':review.id,'release_id':release.id,'run_id':candidate.id,**body.model_dump(),'evidence':evidence}

def report_markdown(detail):
    def cell(v):return html.escape(str(v)).replace('|','&#124;').replace('\n',' ')
    lines=['# 릴리스 검토 보고서','',f"- 릴리스: {cell(detail['name'])} / {detail['id']}",
           f"- 결과 구분: {'시나리오 데모 (고정 예측)' if detail['scenario_demo'] else '실제 로컬 모델 평가'}",
           f"- 시스템 판정: {detail['system_verdict']}",f"- 일반 승인 가능: {detail['approval_allowed']}",'',
           '| 요구사항 | 버전 | 정책 버전 | 적용 기준 | 관측값 | 판정 | 근거 실행 |','|---|---:|---|---|---|---|---|']
    for r in detail['requirements']:
        req=r['requirement'];p=req['policy'];v=r['verdict']
        lines.append('| '+' | '.join(cell(x) for x in [req['identifier'],req['version'],f"{p['identifier']} v{p['version']}",p['config'],v.get('observed','없음'),v['status_label'],r['evidence_run_id'] or '없음'])+' |')
        lines.extend(['- 위반 기준: '+cell(x) for x in v.get('reasons',[])])
        lines.append('- 대표 위반 사례 ID: '+cell(', '.join(v.get('violation_case_ids',[])) or '없음'))
    for title,key in [('최초 실패 실행','initial_run'),('수정 후보 실행','candidate_run')]:
        run=detail[key]
        if not run:continue
        snap=run['snapshot'];result=run['result'] or {}
        lines.extend(['',f'## {title}',f"- 실행 ID: {run['id']}",f"- 데이터셋 버전: {snap['dataset_version']}",
            f"- 모델: {cell(snap['baseline_version'])} → {cell(snap['candidate_version'])}",f"- 커밋: {cell(snap['commit_sha'])}",
            '- 유효 모델 설정: '+cell(snap.get('effective_spec',{})), '- 주요 지표: '+cell({k:result.get(k) for k in ['baseline','candidate','recommendation','reasons']})])
    lines.extend(['','## 동일 조건 비교',cell(detail['comparison']),'','## 재현 사례 / 수정 미사용 사례'])
    for row in detail['reproduction']['used_cases']:
        lines.append('- '+cell(f"원본 {row['source_run_id']} / {row['source_case_id']} → 대상 버전 {row['target_dataset_version']} / {row['candidate_case_id']}: {row['initial_prediction']} → {row['candidate_prediction']} ({row['status']})"))
    lines.extend([cell(detail['reproduction']['unused_subset']),'- 독립 평가 세트: '+cell(detail['independent_evaluation'])])
    lines.extend(['','## 검토자 최종 결정'])
    if not detail['reviews']:lines.append('- 결정 미기록')
    for review in detail['reviews']:
        lines.append('- '+cell(f"{review['decision']} / {review['reviewer']} / {review['reason']} / 근거 실행 {review['run_id']}"))
    lines.extend(['','## 승인 제한',*['- '+cell(x) for x in detail['approval_restrictions']]])
    return '\n'.join(lines)+'\n'

@router.post('/releases/{release_id}/exports',status_code=201)
def export_release(release_id:str):
    with Session() as s:
        release=s.get(Release,release_id)
        if not release:raise HTTPException(404,'릴리스 검토 없음')
        detail=release_detail_in_session(s,release)
        exported_at=now();detail['exported_at']=exported_at
        artifact=ReleaseExport(id=str(uuid4()),release_id=release.id,snapshot=detail,markdown=report_markdown(detail),created_at=exported_at)
        s.add(artifact);s.commit()
        return {'id':artifact.id,'json_url':f'/release-exports/{artifact.id}?format=json','markdown_url':f'/release-exports/{artifact.id}?format=markdown'}

@router.get('/release-exports/{export_id}')
def download_export(export_id:str,format:Literal['json','markdown']='json'):
    with Session() as s:
        artifact=s.get(ReleaseExport,export_id)
        if not artifact:raise HTTPException(404,'보고서 없음')
        content=artifact.markdown if format=='markdown' else json.dumps(artifact.snapshot,ensure_ascii=False,indent=2)
        return Response(content=content,media_type='text/markdown' if format=='markdown' else 'application/json',
            headers={'Content-Disposition':f'attachment; filename="release-{export_id}.{ "md" if format=="markdown" else "json" }"'})
