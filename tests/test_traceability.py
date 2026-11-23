import copy
import json
import pytest
from sqlalchemy import select,func
from backend import db,evaluation,main,traceability
from scripts.pr_check import run_check
from test_platform import client,start

REF={'identifier':'REQ-REFUND-001','version':1}

def setup(c):
    assert c.post('/requirements/sample').status_code==201
    ds=c.post('/datasets/sample').json()['id']
    return ds

def evaluate(c,ds,variant='original',refs=None,key=None,**kwargs):
    body={'dataset_id':ds,'mode':'scenario','scenario_variant':variant,'commit_sha':'repair-'+variant,'requirements':[REF] if refs is None else refs,**kwargs}
    response=start(c,body,key=key or ('run-'+variant))
    assert response.status_code==202,response.text
    run_id=response.json()['run_id'];evaluation.evaluate(run_id)
    return c.get('/runs/'+run_id).json()

def release(c,initial=None,candidate=None,refs=None,sources=None,**kwargs):
    res=c.post('/releases',json={'name':'릴리스 검토','initial_run_id':initial,'candidate_run_id':candidate,
          'requirements':[REF] if refs is None else refs,'reproduction_sources':sources or [],**kwargs})
    assert res.status_code==201,res.text
    return res.json()

def decide(c,release_id,decision='approve'):
    return c.post(f'/releases/{release_id}/reviews',json={'reviewer':'QA','decision':decision,'reason':'기준과 근거 원문 확인'})

def test_requirement_policy_snapshots_survive_revision(client):
    c,_=client;ds=setup(c);old=evaluate(c,ds)
    result=old['result']['requirements'][0]
    assert old['snapshot']['policy']=={'refund_min_recall':.85,'refund_max_drop':.05}
    assert result['verdict']['status']=='failed'
    assert result['verdict']['observed']['candidate_refund_recall']==.6
    assert result['verdict']['violation_case_ids']==['eval-008','eval-009']
    policy={'identifier':'POL-REFUND-001','version':2,'config':{'refund_min_recall':.5,'refund_max_drop':.5}}
    assert c.post('/policies',json=policy).status_code==201
    req=c.get('/requirements').json()[0]
    newer={k:req[k] for k in ['identifier','title','verification_condition','owner','status','mandatory']}
    newer.update(version=2,policy_identifier='POL-REFUND-001',policy_version=2)
    assert c.post('/requirements',json=newer).status_code==201
    current=evaluate(c,ds,refs=[{'identifier':REF['identifier'],'version':2}],key='revision')
    assert current['result']['requirements'][0]['verdict']['status']=='passed'
    assert c.get('/runs/'+old['id']).json()==old
    detail=c.get('/requirements/REQ-REFUND-001/versions/1').json()
    assert detail['evidence'][0]['verdict']==result['verdict']
    assert c.post('/policies',json={**policy,'version':1}).status_code==409
    assert c.post('/requirements',json={**newer,'version':1}).status_code==409

@pytest.mark.parametrize('state',['unverified','unevaluable','failed'])
def test_required_nonpass_blocks_release_approval(client,state):
    c,_=client;ds=setup(c)
    if state=='unevaluable':
        ds=c.post('/datasets',files={'file':('no-refund.csv','case_id,text,expected_label\nx,배송 문의,배송\n'.encode())}).json()['id']
        run=evaluate(c,ds,mode='local')
    else:run=evaluate(c,ds,refs=[] if state=='unverified' else [REF])
    item=release(c,candidate=run['id'])
    assert item['requirements'][0]['verdict']['status']==state
    assert not item['approval_allowed']
    blocked=decide(c,item['id'])
    assert blocked.status_code==409 and blocked.json()['detail']['restrictions']
    assert decide(c,item['id'],'hold').status_code==201
    if state=='unverified':
        assert c.get('/requirements/REQ-REFUND-001/versions/1').json()['status_label']=='미검증'

def test_regression_links_deduplicate_without_changing_dataset(client):
    c,sessions=client;ds=setup(c);run=evaluate(c,ds)
    before=c.get('/datasets/'+ds).json()
    body={'target_dataset_id':ds,'case_ids':['eval-008','eval-008','eval-009']}
    first=c.post(f"/runs/{run['id']}/regression-links",json=body).json()
    again=c.post(f"/runs/{run['id']}/regression-links",json=body).json()
    assert first['created_links']==2 and again['created_links']==0
    after=c.get('/datasets/'+ds).json()
    assert before['cases']==after['cases'] and before['version']==after['version']
    assert len(after['sources'])==2
    assert {x['target_dataset_version'] for x in first['links']}=={before['version']}
    with sessions() as s:assert s.scalar(select(func.count()).select_from(db.CaseSource))==2

def test_same_conditions_correction_comparison_review_and_frozen_report(client):
    c,_=client;ds=setup(c);a=evaluate(c,ds);b=evaluate(c,ds,'repaired')
    c.post(f"/runs/{a['id']}/regression-links",json={'target_dataset_id':ds,'case_ids':['eval-008','eval-009']})
    sources=[{'source_run_id':a['id'],'source_case_id':i} for i in ['eval-008','eval-009']]
    item=release(c,a['id'],b['id'],sources=sources+sources)
    assert item['approval_allowed'] and item['comparison']['allowed']
    assert item['comparison']['deltas']['accuracy']==pytest.approx(.1)
    assert item['comparison']['deltas']['refund_recall']==pytest.approx(.4)
    assert all(r['status']=='passed' for r in item['reproduction']['used_cases'])
    assert len(item['reproduction']['used_cases'])==2
    assert item['reproduction']['unused_subset']['count']==18
    assert item['independent_evaluation']['status']=='unverified'
    review=decide(c,item['id']).json()
    assert review['run_id']==b['id'] and review['evidence']['initial_run_id']==a['id']
    artifact=c.post(f"/releases/{item['id']}/exports").json()
    snapshot=c.get(artifact['json_url']).json();md=c.get(artifact['markdown_url']).text
    assert snapshot['candidate_run']['snapshot']==b['snapshot']
    assert snapshot['initial_run']['id']==a['id']
    assert snapshot['requirements'][0]['requirement']['version']==1
    assert snapshot['candidate_run']['result']==b['result']
    assert '시나리오 데모' in md and a['id'] in md and b['id'] in md and 'eval-008' in md
    assert 'approve' in md and '기준과 근거 원문 확인' in md
    decide(c,item['id'],'hold')
    assert c.get(artifact['json_url']).json()==snapshot

def test_dataset_or_policy_version_change_disables_direct_comparison(client):
    c,_=client;ds=setup(c);a=evaluate(c,ds)
    child=c.post(f"/runs/{a['id']}/dataset-versions",json={'base_dataset_id':ds,'case_ids':['eval-008']}).json()
    b=evaluate(c,child['id'],mode='local',key='new-dataset')
    item=release(c,a['id'],b['id'])
    assert not item['comparison']['allowed'] and item['comparison']['deltas'] is None
    assert any('テスト' in x or '테스트 세트 버전' in x for x in item['comparison']['restriction_reasons'])
    c.post('/policies',json={'identifier':'POL-REFUND-001','version':2,'config':{'refund_min_recall':.85,'refund_max_drop':.05}})
    req=c.get('/requirements').json()[0]
    newer={k:req[k] for k in ['identifier','title','verification_condition','owner','status','mandatory']}
    newer.update(version=2,policy_identifier='POL-REFUND-001',policy_version=2)
    c.post('/requirements',json=newer)
    d=evaluate(c,ds,'repaired',refs=[{'identifier':REF['identifier'],'version':2}],key='policy-two')
    item=release(c,a['id'],d['id'],refs=[{'identifier':REF['identifier'],'version':2}])
    assert not item['comparison']['allowed'] and item['comparison']['deltas'] is None
    assert any('정책 버전' in x for x in item['comparison']['restriction_reasons'])

def test_cli_reuses_requirement_bound_evaluation(client,monkeypatch):
    c,_=client;ds=setup(c);monkeypatch.setattr(main,'dispatch',evaluation.evaluate)
    body={'dataset_id':ds,'mode':'scenario','commit_sha':'pr-req','requirements':[REF]}
    a=run_check(c,body);b=run_check(c,body)
    assert a['exit_code']==1 and a['run_id']==b['run_id']
    assert a['snapshot']['requirements'][0]['policy']['version']==1

def test_unknown_or_duplicate_requirement_version_rejected(client):
    c,_=client;ds=setup(c)
    assert start(c,{'dataset_id':ds,'requirements':[REF,REF]}).status_code==422
    assert start(c,{'dataset_id':ds,'requirements':[{'identifier':REF['identifier'],'version':99}]}).status_code==404

def test_holdout_with_used_cases_is_not_independent(client):
    c,_=client;ds=setup(c);a=evaluate(c,ds);b=evaluate(c,ds,'repaired')
    c.post(f"/runs/{a['id']}/regression-links",json={'target_dataset_id':ds,'case_ids':['eval-008']})
    item=release(c,a['id'],b['id'],holdout_run_id=b['id'],sources=[{'source_run_id':a['id'],'source_case_id':'eval-008'}])
    assert item['independent_evaluation']['status']=='unevaluable'
    assert any('수정 사용 사례' in x for x in item['independent_evaluation']['reasons'])

def test_run_only_review_cannot_override_release_gate(client):
    c,_=client;ds=setup(c);a=evaluate(c,ds)
    item=release(c,candidate=a['id'])
    assert c.post(f"/runs/{a['id']}/reviews",json={'reviewer':'QA','decision':'approve','reason':'실행 단독 기록'}).status_code==201
    after=c.get('/releases/'+item['id']).json()
    assert not after['approval_allowed'] and after['reviews']==[]
    assert decide(c,item['id']).status_code==409

def test_draft_required_version_is_not_counted_as_passed(client):
    c,_=client;ds=setup(c)
    req=c.get('/requirements').json()[0]
    payload={k:req[k] for k in ['identifier','title','verification_condition','owner','status','mandatory']}
    payload.update(version=2,policy_identifier='POL-REFUND-001',policy_version=1,status='draft')
    assert c.post('/requirements',json=payload).status_code==201
    refs=[{'identifier':REF['identifier'],'version':2}]
    run=evaluate(c,ds,'repaired',refs=refs)
    item=release(c,candidate=run['id'],refs=refs)
    assert item['requirements'][0]['verdict']['status']=='unverified' and not item['approval_allowed']

def test_separate_unused_holdout_is_reported_independently(client):
    c,_=client;ds=setup(c);a=evaluate(c,ds)
    candidate=evaluate(c,ds,mode='local',key='local-repair',commit_sha='same-repair-sha')
    c.post(f"/runs/{a['id']}/regression-links",json={'target_dataset_id':ds,'case_ids':['eval-008']})
    csv='case_id,text,expected_label\nh1,환불 신청합니다,환불\nh2,주문 취소 환불 부탁드립니다,환불\n'
    holdout_ds=c.post('/datasets',files={'file':('holdout.csv',csv.encode())}).json()['id']
    holdout=evaluate(c,holdout_ds,mode='local',key='holdout',commit_sha='same-repair-sha')
    item=release(c,a['id'],candidate['id'],holdout_run_id=holdout['id'],sources=[{'source_run_id':a['id'],'source_case_id':'eval-008'}])
    independent=item['independent_evaluation']
    assert independent['status']=='evaluated' and independent['reasons']==[]
    assert independent['run']['id']==holdout['id']
    assert independent['run']['snapshot']['dataset_version']!=candidate['snapshot']['dataset_version']
