import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4
import pytest
from sqlalchemy import select,func,create_engine,event
from fastapi.testclient import TestClient
from backend import db,main,ivd,ivd_changes as changes
from backend.ivd_models import ProductRevision,Package,ChangeRequest
from test_platform import client

def baseline(c,product='HIV',market='EU'):
    c.post('/ivd/sample')
    p=c.post('/ivd/packages',json={'product_id':f'IVD-{product}-DEMO','market':market,'basis':'fictional' if market=='KR' else 'official'}).json()
    materials=c.get(f'/ivd/products/IVD-{product}-DEMO/materials').json()
    perf=next((e for e in materials['evidence'] if e['key']=='performance'),None)
    if not perf:perf=c.post(f'/ivd/products/IVD-{product}-DEMO/evidence',json={'key':'performance','title':'가상 자료','summary':'가상 메타데이터만; 실제 성능값 없음','citation':'가상://성능 §1'}).json()
    c.post(f"/ivd/packages/{p['id']}/regulatory-review",json={'reviewer':'시연 검토자','classification':'가상 분류','submission_route':'가상 검토 경로','rationale':'가상 제품 내부 검토 예시','source_ids':['EU-IVDR' if market=='EU' else 'KR-MFDS'],'fictional_review':True})
    for m in p['mappings']:
        r=c.patch(f"/ivd/packages/{p['id']}/requirements/{m['key']}",json={'document_id':m['document']['id'],'evidence_ids':[perf['id']] if m['section']=='performance' else [e['id'] for e in m['evidence']],'applicability':'applicable','state':'satisfied','reviewer':'QA','rationale':'가상 자료 등록 범위 확인'})
        assert r.status_code==200,r.text
    r=c.post(f"/ivd/packages/{p['id']}/complete",json={'reviewer':'QA'});assert r.status_code==200,r.text
    return r.json()

def create(c,packages,fields=None,replacements=None):
    p=packages[0];r=c.post('/ivd/changes',json={'product_id':p['product']['id'],'base_revision_id':p['product_revision_id'],
        'changes':fields or [],'evidence_replacements':replacements or {},'baseline_packages':{x['market']:x['id'] for x in packages},'reason':'가상 제품 변경 시연','requester':'요청자'})
    assert r.status_code==201,r.text
    return r.json()
def assess(c,id):
    r=c.post(f'/ivd/changes/{id}/assess',json={'reviewer':'QA'});assert r.status_code==200,r.text
    assert c.post(f'/ivd/changes/{id}/start-review',json={'reviewer':'QA'}).status_code==200
    return r.json()
def market(c,id,name):
    r=c.post(f'/ivd/changes/{id}/markets/{name}/decision',json={'reviewer':'시장 검토자','reason':name+' 가상 제품 변경점과 등록 근거 확인','source_ids':['EU-IVDR' if name=='EU' else 'KR-MFDS'],'legal_procedure':'가상 변경 검토 예시; 실제 규제 절차 미확정','submission_required':None,'fictional_review':True})
    assert r.status_code==200,r.text
    return r.json()
def retain(c,id,item):
    r=c.post(f"/ivd/changes/{id}/items/{item['id']}/decision",json={'reviewer':'QA','choice':'retain','reason':'연결 자료를 수동 확인하여 기존 자료 유지'})
    assert r.status_code==200,r.text
def prepare_name(c,p,name='가상 제품명 개정 예시'):
    request=create(c,[p],fields=[{'field':'name','before':p['product']['name'],'after':name}]);scoped=assess(c,request['id'])
    for item in scoped['items']:retain(c,request['id'],item)
    market(c,request['id'],p['market'])
    return request

def test_evidence_reference_impact_is_exact_and_idempotent(client):
    c,_=client;p=baseline(c);before=copy.deepcopy(p)
    old=next(m for m in p['mappings'] if m['section']=='performance')['evidence'][0]
    new=c.post(f"/ivd/products/{p['product']['id']}/evidence",json={'key':old['key'],'title':'가상 증빙 r2','summary':'새 등록 위치 메타데이터','citation':'가상://r2 §1','previous_id':old['id']}).json()
    request=create(c,[p],replacements={old['id']:new['id']})
    assert c.get('/ivd/packages/'+p['id']).json()==before
    result=assess(c,request['id']);assert len(result['items'])==1
    item=result['items'][0];assert item['section']=='performance' and item['evidence'][0]['id']==old['id']
    assert item['reasons'][0]['kind']=='evidence_reference'
    assert len(c.post(f"/ivd/changes/{request['id']}/assess",json={'reviewer':'QA'}).json()['items'])==1
    assert c.post(f"/ivd/changes/{request['id']}/items/{item['id']}/decision",json={'reviewer':'QA','choice':'revise','reason':'새 증빙 위치 확인','evidence_replacements':{old['id']:new['id']}}).status_code==200
    market(c,request['id'],'EU')
    done=c.post(f"/ivd/changes/{request['id']}/approve",json={'reviewer':'최종 QA'})
    assert done.status_code==200,done.text
    result=done.json();assert result['product_revision']==2
    final=c.get('/ivd/packages/'+result['packages']['EU']['id']).json()
    assert next(m for m in final['mappings'] if m['section']=='performance')['evidence'][0]['id']==new['id']
    assert c.get('/ivd/packages/'+p['id']).json()==before
    assert c.post(f"/ivd/changes/{request['id']}/approve",json={'reviewer':'최종 QA'}).json()==result

def test_name_impacts_markets_and_product_history(client):
    c,_=client;kr=baseline(c,'COVID','KR');eu=baseline(c,'COVID','EU');c.post('/ivd/change-rules/sample')
    req=create(c,[kr,eu],fields=[{'field':'name','before':kr['product']['name'],'after':'COVID 가상 제품 v2'}]);d=assess(c,req['id'])
    assert {(i['market'],i['section']) for i in d['items']}=={(m,s) for m in ['KR','EU'] for s in ['overview','labeling']}
    after_kr=market(c,req['id'],'KR')
    assert next(m for m in after_kr['markets'] if m['market']=='EU')['judgment'] is None
    before_kr=copy.deepcopy(kr);before_eu=copy.deepcopy(eu)
    for item in d['items']:
        doc=item['document'];new=c.post(f"/ivd/products/{kr['product']['id']}/documents",json={'section':item['section'],'content':'등록된 가상 제품명을 COVID 가상 제품 v2로 수정한 문서','citation':'가상 등록 문서의 제품명 필드'}).json()
        assert c.post(f"/ivd/changes/{req['id']}/items/{item['id']}/decision",json={'reviewer':'QA','choice':'revise','reason':'변경된 제품명 인용 반영','document_id':new['id']}).status_code==200
    market(c,req['id'],'EU')
    result=c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'});assert result.status_code==200,result.text
    assert set(result.json()['packages'])=={'KR','EU'}
    assert c.get('/ivd/packages/'+kr['id']).json()==before_kr
    assert c.get('/ivd/packages/'+eu['id']).json()==before_eu
    assert c.get('/ivd/products').json()[0]['name']=='COVID 가상 제품 v2'

def test_missing_rule_manual_item_and_decision_reasons(client):
    c,_=client;p=baseline(c)
    req=create(c,[p],fields=[{'field':'storage_condition','before':None,'after':'가상 보관 필드 개정'}]);d=assess(c,req['id'])
    assert len(d['items'])==1 and d['items'][0]['manual_check']
    item=d['items'][0]
    bad=c.post(f"/ivd/changes/{req['id']}/items/{item['id']}/decision",json={'reviewer':'QA','choice':'not_applicable','reason':' '})
    assert bad.status_code==422
    blocked=c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'})
    assert blocked.status_code==409 and any(x['id']==item['id'] for x in blocked.json()['detail']['blockers'])
    retain(c,req['id'],item)

def test_corrections_and_existing_supplement_gate(client):
    c,_=client;p=baseline(c);c.post('/ivd/change-rules/sample');req=prepare_name(c,p)
    original=copy.deepcopy(p)
    response=c.post(f"/ivd/changes/{req['id']}/markets/EU/requests",json={'section':'overview','reason':'추가 가상 메타데이터 확인 필요','owner':'작성자','due_date':'2026-12-01','reviewer':'QA'})
    assert response.status_code==201,response.text
    work=response.json();assert work['work_package_id']!=p['id']
    assert c.get('/ivd/packages/'+p['id']).json()==original
    assert c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'}).status_code==409
    c.post(f"/ivd/requests/{work['id']}/answer",json={'reviewer':'작성자','answer':'등록 자료를 확인한 수동 답변','evidence_ids':[]})
    c.post(f"/ivd/requests/{work['id']}/start-review",json={'reviewer':'QA'})
    c.post(f"/ivd/requests/{work['id']}/close",json={'reviewer':'QA','confirmed':True,'reason':'답변 및 자료 확인'})
    correction=c.post(f"/ivd/changes/{req['id']}/corrections",json={'reviewer':'QA','reason':'유지 판단의 설명 보강 요청'}).json()
    assert correction['status']=='changes_requested'
    assert c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'}).status_code==409
    rid=correction['corrections'][0]['id']
    assert c.post(f"/ivd/changes/{req['id']}/corrections/{rid}/resolve",json={'reviewer':'QA','response':'유지 근거 설명을 확인했습니다'}).status_code==200
    approved=c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'});assert approved.status_code==200,approved.text

def test_stale_revision_conflict_and_no_duplicate_outcomes(client):
    c,sessions=client;p=baseline(c);c.post('/ivd/change-rules/sample')
    a=prepare_name(c,p,'가상 변경 A');b=prepare_name(c,p,'가상 변경 B')
    first=c.post(f"/ivd/changes/{a['id']}/approve",json={'reviewer':'QA'});assert first.status_code==200,first.text
    conflict=c.post(f"/ivd/changes/{b['id']}/approve",json={'reviewer':'QA'})
    assert conflict.status_code==409 and conflict.json()['detail']['re_review_required']
    assert c.post(f"/ivd/changes/{a['id']}/approve",json={'reviewer':'QA'}).json()==first.json()
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(ProductRevision).where(ProductRevision.product_id==p['product']['id']))==2
        assert s.scalar(select(func.count()).select_from(Package).where(Package.family_id==p['family_id']))==2

def test_regulatory_source_scope_and_ai_ids(client,monkeypatch):
    c,_=client;p=baseline(c,'COVID','KR');req=create(c,[p],fields=[{'field':'name','before':p['product']['name'],'after':'가상 이름'}]);d=assess(c,req['id'])
    payload={'reviewer':'QA','reason':'공식 근거 검토','source_ids':['KR-MFDS'],'legal_procedure':'미확인','submission_required':False,'fictional_review':False}
    assert c.post(f"/ivd/changes/{req['id']}/markets/KR/decision",json=payload).status_code==409
    before=c.get('/ivd/changes/'+req['id']).json()
    monkeypatch.setattr(changes,'summary_provider',lambda _: {'sentences':[{'text':'연결된 가상 자료 확인 필요','evidence_ids':['outside-id']}]})
    assert c.post(f"/ivd/changes/{req['id']}/summary",json={'provider':'huggingface'}).status_code==422
    assert c.get('/ivd/changes/'+req['id']).json()==before
    monkeypatch.setattr(changes,'summary_provider',lambda _: {'sentences':[{'text':'가상 변경 검토','evidence_ids':[d['items'][0]['id']]}]})
    assert c.post(f"/ivd/changes/{req['id']}/summary",json={'provider':'huggingface'}).status_code==200
    assert c.post(f"/ivd/changes/{req['id']}/summary",json={'provider':'manual'}).json()['ai_used'] is False

def test_change_report_frozen_and_matches_revisions(client,monkeypatch):
    c,_=client;p=baseline(c);c.post('/ivd/change-rules/sample');req=prepare_name(c,p)
    result=c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'}).json()
    monkeypatch.delenv('HF_TOKEN',raising=False)
    artifact=c.post(f"/ivd/changes/{req['id']}/exports").json();report=c.get(artifact['json_url']).json();md=c.get(artifact['markdown_url']).text
    assert report['result']==result and report['base_revision']['id']==p['product_revision_id']
    assert '가상 제품 · 검토용 예시' in md and result['product_revision_id'] in md
    assert c.post(f"/ivd/changes/{req['id']}/corrections",json={'reviewer':'QA','reason':'완료 후 수정 시도'}).status_code==409
    assert c.get(artifact['json_url']).json()==report

def test_package_baseline_conflict_without_product_revision_increment(client):
    c,_=client;p=baseline(c);c.post('/ivd/change-rules/sample');req=prepare_name(c,p)
    assert c.post(f"/ivd/packages/{p['id']}/versions",json={'reviewer':'다른 검토자'}).status_code==201
    response=c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'})
    assert response.status_code==409 and response.json()['detail']['re_review_required']
    assert c.get(f"/ivd/products/{p['product']['id']}/revisions").json()['current_revision']==1

def test_multi_market_failure_rolls_back_product_and_packages(client,monkeypatch):
    c,sessions=client;kr=baseline(c,'COVID','KR');eu=baseline(c,'COVID','EU');c.post('/ivd/change-rules/sample')
    req=create(c,[kr,eu],fields=[{'field':'name','before':kr['product']['name'],'after':'가상 롤백 시험'}]);d=assess(c,req['id'])
    for i in d['items']:retain(c,req['id'],i)
    market(c,req['id'],'KR');market(c,req['id'],'EU')
    original=ivd.clone_version;calls=[]
    def fail_second(*args):
        calls.append(1)
        if len(calls)==2:raise changes.HTTPException(409,'두 번째 시장 패키지 생성 실패 주입')
        return original(*args)
    monkeypatch.setattr(ivd,'clone_version',fail_second)
    assert c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'}).status_code==409
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(ProductRevision).where(ProductRevision.product_id==kr['product']['id']))==1
        assert s.scalar(select(func.count()).select_from(Package).where(Package.product_id==kr['product']['id']))==2
    monkeypatch.setattr(ivd,'clone_version',original)
    assert c.post(f"/ivd/changes/{req['id']}/approve",json={'reviewer':'QA'}).status_code==200

def test_rule_snapshots_and_intended_use_mapping(client):
    c,_=client;p=baseline(c);c.post('/ivd/change-rules/sample')
    req=create(c,[p],fields=[{'field':'intended_use','before':None,'after':'가상 사용 목적 메타데이터 개정'}]);d=assess(c,req['id'])
    assert {i['section'] for i in d['items']}=={'overview','intended_use','labeling','performance'}
    before=copy.deepcopy(d['items'])
    c.post('/ivd/change-rules',json={'field':'intended_use','market':'EU','section':'overview','version':2,'reason':'새 가상 연결 규칙'})
    assert c.get('/ivd/changes/'+req['id']).json()['items']==before

def test_actual_concurrent_confirmation_has_one_winner(monkeypatch):
    # File-backed SQLite and separate connections exercise a real CAS race.
    root=Path('reports')/('test-change-'+uuid4().hex);root.mkdir(parents=True)
    engine=create_engine('sqlite:///'+str(root/'concurrency.db'),connect_args={'check_same_thread':False,'timeout':15})
    db.Base.metadata.create_all(engine);sessions=db.sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(ivd,'Session',sessions);monkeypatch.setattr(changes,'Session',sessions)
    with TestClient(main.app) as c:
        p=baseline(c);c.post('/ivd/change-rules/sample');a=prepare_name(c,p,'가상 동시 A');b=prepare_name(c,p,'가상 동시 B')
        barrier=Barrier(2);original=changes.compare_and_swap_product
        def race(*args):barrier.wait(timeout=10);return original(*args)
        monkeypatch.setattr(changes,'compare_and_swap_product',race)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda id:c.post(f'/ivd/changes/{id}/approve',json={'reviewer':'QA'}),[a['id'],b['id']]))
        assert sorted(r.status_code for r in outcomes)==[200,409],[r.text for r in outcomes]
        with sessions() as s:
            assert s.scalar(select(func.count()).select_from(ProductRevision).where(ProductRevision.product_id==p['product']['id']))==2
            assert s.scalar(select(func.count()).select_from(Package).where(Package.family_id==p['family_id']))==2
    engine.dispose()
