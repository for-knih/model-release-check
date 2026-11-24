import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from fastapi import FastAPI, UploadFile, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import Session, Dataset, Case, Run, Review, Analysis, CaseSource, RunRequirement
from .models import DATA, LABELS, LocalAdapter
from .specs import BaselineConfig, CandidateConfig, effective_spec, fingerprint
from .traceability import Ref, resolve_requirements, combined_policy, router as traceability_router

app = FastAPI(title='AI 모델 변경 검증 플랫폼')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://localhost:8080', 'http://127.0.0.1:5173', 'http://127.0.0.1:8080'], allow_methods=['*'], allow_headers=['*'])

class Policy(BaseModel):
    refund_min_recall: float = Field(default=.8, ge=0, le=1)
    refund_max_drop: float = Field(default=.1, ge=0, le=1)

class Request(BaseModel):
    dataset_id: str
    mode: Literal['local', 'scenario'] = 'local'
    candidate_adapter: Literal['local', 'huggingface'] = 'local'
    policy: Policy = Field(default_factory=Policy)
    baseline_config: BaselineConfig = Field(default_factory=BaselineConfig)
    candidate_config: CandidateConfig | None = None
    commit_sha: str = Field(default='manual', min_length=1, max_length=100)
    baseline_version_label: str = Field(default='keyword-v1', max_length=200)
    candidate_version_label: str = Field(default='candidate-v1', max_length=200)
    prompt_version: str = Field(default='none', max_length=200)
    requirements: list[Ref] = Field(default_factory=list,max_length=30)
    scenario_variant: Literal['original','repaired'] = 'original'

class Decision(BaseModel):
    reviewer: str = Field(min_length=1, max_length=100)
    decision: Literal['approve', 'hold']
    reason: str = Field(default='', max_length=4000)

def parse_csv(content):
    try:
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')), strict=True)
        if reader.fieldnames != ['case_id', 'text', 'expected_label']:
            raise HTTPException(422, [{'row': 1, 'reason': '헤더는 case_id,text,expected_label 순서여야 합니다'}])
        rows, errors, seen = [], [], set()
        for row in reader:
            number = reader.line_num
            if None in row or any(not (row.get(k) or '').strip() for k in reader.fieldnames):
                errors.append({'row': number, 'reason': '필수 값 누락 또는 열 개수 오류'})
                continue
            row = {k: v.strip() for k, v in row.items()}
            if row['case_id'] in seen:
                errors.append({'row': number, 'reason': '중복 ID: ' + row['case_id']})
            seen.add(row['case_id'])
            if row['expected_label'] not in LABELS:
                errors.append({'row': number, 'reason': '허용되지 않은 라벨'})
            rows.append(row)
        if not rows and not errors:
            errors.append({'row': 2, 'reason': '평가 사례가 없습니다'})
        if errors:
            raise HTTPException(422, errors)
        return rows
    except (UnicodeDecodeError, csv.Error) as e:
        raise HTTPException(422, [{'row': 1, 'reason': 'UTF-8 CSV 형식 오류'}]) from e

def register(content, name):
    rows = parse_csv(content)
    version = hashlib.sha256(content).hexdigest()
    with Session() as s:
        existing = s.scalar(select(Dataset).where(Dataset.name == name, Dataset.version == version))
        if existing:
            return {'id': existing.id, 'name': name, 'version': version, 'count': len(rows)}
        ds = Dataset(id=str(uuid4()), name=name, version=version)
        s.add(ds)
        s.flush()
        s.add_all(Case(dataset_id=ds.id, **r) for r in rows)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            ds = s.scalar(select(Dataset).where(Dataset.name == name, Dataset.version == version))
        return {'id': ds.id, 'name': name, 'version': version, 'count': len(rows)}

@app.post('/datasets', status_code=201)
async def upload(file: UploadFile):
    content = await file.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(413, 'CSV 최대 2MB')
    return register(content, file.filename or 'upload.csv')

@app.post('/datasets/sample', status_code=201)
def sample():
    return register((DATA / 'evaluation.csv').read_bytes(), '쇼핑몰 합성 평가 세트')

@app.get('/datasets')
def list_datasets(version: str | None = None):
    with Session() as s:
        query = select(Dataset)
        if version:
            query = query.where(Dataset.version == version)
        return [{'id':d.id, 'name':d.name, 'version':d.version, 'parent_id':d.parent_id} for d in s.scalars(query)]

@app.get('/datasets/{dataset_id}')
def dataset_detail(dataset_id: str):
    with Session() as s:
        ds = s.get(Dataset, dataset_id)
        if not ds:
            raise HTTPException(404, '데이터셋 없음')
        return {'id':ds.id, 'version':ds.version, 'name':ds.name, 'parent_id':ds.parent_id,
                'cases':[{'case_id':c.case_id,'text':c.text,'expected_label':c.expected_label} for c in s.scalars(select(Case).where(Case.dataset_id==ds.id).order_by(Case.id))],
                'sources':[{'case_id':s.get(Case,x.case_id).case_id,'source_run_id':x.source_run_id,'source_case_id':x.source_case_id} for x in s.scalars(select(CaseSource).where(CaseSource.dataset_id==ds.id))]}

@app.post('/run-specs')
def resolve_spec(body: Request):
    with Session() as s:
        dataset = s.get(Dataset, body.dataset_id)
        if not dataset:
            raise HTTPException(404, '데이터셋 없음')
        requirements = resolve_requirements(s,body.requirements)
        policy = combined_policy(requirements,body.policy.model_dump())
        spec = effective_spec(body.model_copy(update={'policy':Policy(**policy)}), dataset)
        if requirements:
            spec['requirements'] = requirements
        return {'effective_spec': spec, 'fingerprint': fingerprint(spec)}

def dispatch(run_id):
    if os.getenv('QUEUE_MODE') == 'thread':
        # Explicit development fallback; Compose always uses Redis + RQ.
        from concurrent.futures import ThreadPoolExecutor
        from .evaluation import evaluate
        executor.submit(evaluate, run_id)
    else:
        from redis import Redis
        from rq import Queue, Retry
        Queue(connection=Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), socket_connect_timeout=2, socket_timeout=2)).enqueue('backend.evaluation.evaluate', run_id, retry=Retry(max=2), job_timeout=300)

from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=1)

@app.post('/runs', status_code=202)
def create_run(body: Request, idempotency_key: str = Header(min_length=1, max_length=200)):
    resolved = resolve_spec(body)
    digest = resolved['fingerprint']
    with Session() as s:
        run = s.scalar(select(Run).where(Run.idempotency_key == idempotency_key).with_for_update())
        if run and run.request_hash != digest:
            raise HTTPException(409, '같은 멱등 키에 다른 요청입니다')
        if not run:
            ds = s.get(Dataset, body.dataset_id)
            if not ds:
                raise HTTPException(404, '데이터셋 없음')
            spec = resolved['effective_spec']
            snapshot = {**body.model_dump(), 'dataset_version': ds.version, 'baseline_version': 'keyword-v1', 'created_at': datetime.now(timezone.utc).isoformat(), 'training_config': {'analyzer': 'char', 'random_state': 42, **spec['candidate_config']}, 'metric_labels': LABELS, 'effective_spec':spec, 'configuration_fingerprint':digest}
            snapshot['policy'] = spec['policy']
            snapshot['requirements'] = spec.get('requirements',[])
            if body.mode == 'scenario':
                fixture = json.loads((DATA / ('scenario_repaired.json' if body.scenario_variant=='repaired' else 'scenario.json')).read_text(encoding='utf-8'))
                if ds.version != hashlib.sha256((DATA / 'evaluation.csv').read_bytes()).hexdigest():
                    raise HTTPException(422, '고정 시나리오는 샘플 평가 세트만 지원합니다')
                snapshot.update(candidate_version='fixed-scenario-v1', baseline_version='fixed-scenario-v1', scenario_predictions=fixture)
                if body.scenario_variant=='repaired':
                    snapshot['candidate_version']='fixed-scenario-repaired-v1'
            else:
                snapshot['candidate_adapter'] = spec['candidate_config']['adapter']
                snapshot['candidate_version'] = spec['candidate_config'].get('model_id') if snapshot['candidate_adapter'] == 'huggingface' else LocalAdapter(spec['candidate_config']).version
                if snapshot['candidate_adapter'] == 'huggingface' and not (snapshot['candidate_version'] and os.getenv('HF_TOKEN')):
                    raise HTTPException(422, 'HF_MODEL_ID와 HF_TOKEN이 필요합니다')
            run = Run(id=str(uuid4()), dataset_id=ds.id, idempotency_key=idempotency_key, request_hash=digest, snapshot=snapshot)
            s.add(run)
            try:
                s.flush()
                s.add_all(RunRequirement(run_id=run.id,requirement_id=r['id'],snapshot=r) for r in snapshot['requirements'])
                s.commit()
            except IntegrityError:
                s.rollback()
                return create_run(body, idempotency_key)
        run_id = run.id
    # Commit first so workers can see the run. Hold row lock while dispatching.
    with Session() as s:
        run = s.get(Run, run_id, with_for_update=True)
        if not run.dispatched:
            try:
                dispatch(run_id)
            except Exception:
                run.error = '큐 등록 실패: 같은 멱등 키로 재요청하세요'
                s.commit()
                raise HTTPException(503, {'run_id': run_id, 'message': run.error})
            run.dispatched, run.error = True, None
            s.commit()
    return {'run_id': run_id, 'status_url': f'/runs/{run_id}'}

@app.get('/runs/{run_id}')
def get_run(run_id: str):
    with Session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, '실행 없음')
        return {'id': run.id, 'status': run.status, 'snapshot': run.snapshot, 'error': run.error, 'result': run.result}

@app.post('/runs/{run_id}/reviews', status_code=201)
def review(run_id: str, body: Decision):
    if not body.reviewer.strip() or (body.decision == 'hold' and not body.reason.strip()):
        raise HTTPException(422, '검토자와 보류 사유를 입력하세요')
    with Session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, '실행 없음')
        if run.status != 'succeeded':
            raise HTTPException(409, '완료된 실행만 검토할 수 있습니다')
        item = Review(run_id=run_id, **body.model_dump(), created_at=datetime.now(timezone.utc).isoformat())
        s.add(item)
        s.commit()
        return {'id': item.id, **body.model_dump(), 'created_at': item.created_at}

@app.get('/runs/{run_id}/reviews')
def reviews(run_id: str):
    with Session() as s:
        if not s.get(Run, run_id):
            raise HTTPException(404, '실행 없음')
        return [{'id': r.id, 'reviewer': r.reviewer, 'decision': r.decision, 'reason': r.reason, 'created_at': r.created_at, 'release_id':r.release_id,'evidence':r.evidence} for r in s.scalars(select(Review).where(Review.run_id == run_id).order_by(Review.id))]

@app.get('/health')
def health():
    with Session() as s:
        s.execute(select(1))
    return {'status': 'ok'}

class AnalysisRequest(BaseModel):
    provider: Literal['local', 'huggingface'] = 'local'

def dispatch_analysis(analysis_id):
    if os.getenv('QUEUE_MODE') == 'thread':
        from .analysis import analyze
        executor.submit(analyze, analysis_id)
    else:
        from redis import Redis
        from rq import Queue, Retry
        Queue(connection=Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), socket_connect_timeout=2, socket_timeout=2)).enqueue('backend.analysis.analyze', analysis_id, retry=Retry(max=1), job_timeout=180)

@app.post('/runs/{run_id}/analyses', status_code=202)
def request_analysis(run_id: str, body: AnalysisRequest):
    from .analysis import PROMPT_VERSION, SYSTEM_PROMPT
    config = {'provider':body.provider, 'prompt_version':PROMPT_VERSION, 'prompt_sha256':fingerprint(SYSTEM_PROMPT)}
    if body.provider=='huggingface':
        config['model_id'] = os.getenv('HF_ANALYSIS_MODEL_ID') or os.getenv('HF_MODEL_ID')
        if not config['model_id'] or not os.getenv('HF_TOKEN'):
            raise HTTPException(422, 'HF_MODEL_ID 또는 HF_ANALYSIS_MODEL_ID와 HF_TOKEN이 필요합니다')
    digest = fingerprint(config)
    with Session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, '실행 없음')
        if run.status != 'succeeded':
            raise HTTPException(409, '완료된 평가만 분석할 수 있습니다')
        item = s.scalar(select(Analysis).where(Analysis.run_id==run_id, Analysis.config_hash==digest))
        if not item:
            item = Analysis(id=str(uuid4()), run_id=run_id, config_hash=digest, config=config, created_at=datetime.now(timezone.utc).isoformat())
            s.add(item)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                return request_analysis(run_id, body)
        task_id = item.id
    with Session() as s:
        item = s.get(Analysis, task_id, with_for_update=True)
        if not item.dispatched:
            try:
                dispatch_analysis(task_id)
            except Exception:
                item.error = '분석 큐 등록 실패: 같은 요청으로 재시도하세요'
                s.commit()
                raise HTTPException(503, {'analysis_id':task_id, 'message':item.error})
            item.dispatched, item.error = True, None
            s.commit()
    return {'analysis_id':task_id}

@app.get('/runs/{run_id}/analyses')
def get_analyses(run_id: str):
    with Session() as s:
        if not s.get(Run, run_id):
            raise HTTPException(404, '실행 없음')
        return [{'id':a.id, 'status':a.status, 'config':a.config, 'result':a.result, 'error':a.error, 'review_only':True} for a in s.scalars(select(Analysis).where(Analysis.run_id==run_id).order_by(Analysis.created_at))]

class AddCases(BaseModel):
    base_dataset_id: str
    case_ids: list[str] = Field(min_length=1, max_length=100)

@app.post('/runs/{run_id}/dataset-versions', status_code=201)
def next_dataset(run_id: str, body: AddCases):
    from .analysis import regressions
    with Session() as s:
        run, base = s.get(Run, run_id), s.get(Dataset, body.base_dataset_id)
        if not run or not base:
            raise HTTPException(404, '실행 또는 기준 데이터셋 없음')
        if run.status != 'succeeded':
            raise HTTPException(409, '완료된 실행만 사용할 수 있습니다')
        failures = {r['case_id']:r for r in regressions(run)}
        selected = sorted(set(body.case_ids))
        if not set(selected)<=failures.keys():
            raise HTTPException(422, '기준만 정답인 실패 사례 ID만 선택하세요')
        old_cases = s.scalars(select(Case).where(Case.dataset_id==base.id).order_by(Case.id)).all()
        # A repeated selection creates the same immutable child, never duplicated rows.
        digest = fingerprint({'parent':base.id, 'source_run_id':run_id, 'selected':selected})
        existing = s.scalar(select(Dataset).where(Dataset.name==base.name, Dataset.version==digest))
        if existing:
            return {'id':existing.id,'version':digest,'parent_id':base.id,'reused':True}
        ds = Dataset(id=str(uuid4()), name=base.name, version=digest, parent_id=base.id)
        s.add(ds)
        s.flush()
        by_content, by_old_id, used_ids = {}, {}, set()
        for c in old_cases:
            identity = (c.text.strip(), c.expected_label)
            copied = by_content.get(identity)
            if not copied:
                copied=Case(dataset_id=ds.id,case_id=c.case_id,text=c.text,expected_label=c.expected_label)
                s.add(copied);s.flush()
                by_content[identity]=copied;used_ids.add(c.case_id)
            by_old_id[c.id]=copied
        origins=set()
        for x in s.scalars(select(CaseSource).where(CaseSource.dataset_id==base.id)):
            s.add(CaseSource(dataset_id=ds.id,case_id=by_old_id[x.case_id].id,source_run_id=x.source_run_id,source_case_id=x.source_case_id))
            origins.add((x.source_run_id,x.source_case_id))
        for case_id in selected:
            row=failures[case_id]
            identity=(row['text'].strip(),row['expected_label'])
            copied=by_content.get(identity)
            if not copied:
                new_id=case_id if case_id not in used_ids else 'added-'+fingerprint({'run':run_id,'case':case_id})[:16]
                copied=Case(dataset_id=ds.id,case_id=new_id,text=row['text'],expected_label=row['expected_label'])
                s.add(copied);s.flush();by_content[identity]=copied;used_ids.add(new_id)
            if (run_id,case_id) not in origins:
                s.add(CaseSource(dataset_id=ds.id,case_id=copied.id,source_run_id=run_id,source_case_id=case_id))
                origins.add((run_id,case_id))
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            return next_dataset(run_id,body)
        return {'id':ds.id,'version':digest,'parent_id':base.id,'count':len(by_content),'reused':False}

app.include_router(traceability_router)
from .ivd import router as ivd_router
app.include_router(ivd_router)
from .ivd_changes import router as ivd_changes_router
app.include_router(ivd_changes_router)
from .ivd_pms import router as ivd_pms_router
app.include_router(ivd_pms_router)
