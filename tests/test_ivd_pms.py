from datetime import timedelta
from test_platform import client
from test_ivd_changes import baseline,prepare_name
from backend import ivd_pms as pms

def post(c,path,body,code=200):
    r=c.post('/ivd'+path,json={'reviewer':'QA',**body});assert r.status_code==code,r.text
    return r.json()

def setup(c,product='HIV',market='EU'):
    p=baseline(c,product,market);pid=p['product']['id']
    lot=post(c,'/lots',{'product_id':pid,'market':market,'number':'LOT-1','package_id':p['id']},201)
    e=c.post(f'/ivd/products/{pid}/evidence',json={'key':'pms-proof','title':'가상 조사 증빙','summary':'가상 제품 · 검토용 예시','citation':'가상://조사'}).json()['id']
    return p,lot,e

def complaint(c,p,lot=None,day=None):
    return post(c,'/complaints',{'product_id':p['product']['id'],'market':p['market'],'lot_number':lot,'received_on':str(day or pms.today()-timedelta(days=2)),'problem_type':'outdated_ifu','description':'가상 이전 설명서 동봉','observed_facts':'합성 사진 메타데이터','owner':'조사자','due_date':str(pms.today()+timedelta(days=30)),'synthetic':True},201)

def capa(c,cp):return post(c,f"/complaints/{cp['id']}/capas",{'title':'가상 CAPA','owner':'담당자','due_date':str(pms.today()+timedelta(days=30))},201)
def action(c,ca):return post(c,f"/capas/{ca['id']}/actions",{'kind':'corrective','description':'가상 포장 확인','owner':'담당자','due_date':str(pms.today()+timedelta(days=30))},201)
def plan(c,ca,start=0):
    t=pms.today()
    return post(c,f"/capas/{ca['id']}/plans",{'before_start':str(t-timedelta(days=10)),'before_end':str(t-timedelta(days=1)),'after_start':str(t+timedelta(days=start)),'after_end':str(t+timedelta(days=start+10)),'before_lot_numbers':['LOT-1'],'after_lot_numbers':['LOT-1'],'data_source':'합성 접수·유통 원장','max_after_rate':0.5},201)
def complete(c,ca,a,e):return post(c,f"/capas/{ca['id']}/actions/{a['id']}/complete",{'note':'가상 실행 확인','evidence_ids':[e]})
def dist(c,ca,lot,p,phase,e,qty=1000):
    return post(c,f"/capas/{ca['id']}/distributions",{'lot_ids':[lot['id']],'period_start':p['definition'][phase+'_start'],'period_end':p['definition'][phase+'_end'],'quantity':qty,'source':'합성 유통 원장','evidence_ids':[e]},201)
def evaluate(c,ca,p,e,key='eval',**kwargs):
    body={'reviewer':'QA','plan_id':p['id'],'as_of':p['definition']['after_end'],'synthetic':True,'result_evidence_ids':[e],**kwargs}
    return c.post(f"/ivd/capas/{ca['id']}/evaluations",json=body,headers={'Idempotency-Key':key})

def test_unknown_lot_confirmation_and_frozen_documents(client):
    c,_=client;p,lot,e=setup(c);cp=complaint(c,p)
    assert cp['status']=='needs_confirmation' and cp['lot'] is None
    confirmed=post(c,f"/complaints/{cp['id']}/confirm-lot",{'lot_id':lot['id'],'reason':'로트 원장 확인'})
    assert confirmed['lot']['snapshot']['mappings']==p['mappings']
    assert confirmed['history'][-1]['action']=='lot_confirmed'
    other=baseline(c,'COVID','EU');wrong=post(c,'/lots',{'product_id':other['product']['id'],'market':'EU','number':'OTHER','package_id':other['id']},201)
    post(c,f"/complaints/{cp['id']}/confirm-lot",{'lot_id':wrong['id'],'reason':'오연결'},422)
    change=prepare_name(c,p)
    post(c,f"/changes/{change['id']}/approve",{})
    assert c.get('/ivd/complaints/'+cp['id']).json()['lot']==confirmed['lot']

def test_duplicate_receipts_and_root_cause_proof(client):
    c,_=client;p,lot,e=setup(c);a=complaint(c,p,'LOT-1');b=complaint(c,p,'LOT-1')
    d=post(c,f"/complaints/{b['id']}/duplicate",{'representative_id':a['id'],'reason':'같은 포장 사건 확인'})
    assert (d['related']['raw_receipts'],d['related']['distinct_incidents'])==(2,1)
    assert c.get('/ivd/complaints?lot=LOT-1&owner=조사자').json()['distinct_incidents']==1
    post(c,f"/complaints/{a['id']}/investigation",{'confirmed_cause':'가상 원인'},422)
    d=post(c,f"/complaints/{a['id']}/investigation",{'hypothesis':'가설','confirmed_cause':'합성 조사로 확인한 원인','evidence_ids':[e]})
    assert d['hypothesis']=='가설' and d['confirmed_cause']['reviewer']=='QA'
    assert d['reporting_review']['deadline_status']=='미확정'

def test_reporting_source_and_deadline_not_automatic(client):
    c,_=client;p,lot,e=setup(c,'COVID','KR');cp=complaint(c,p,'LOT-1')
    body={'required':True,'source_ids':['KR-MFDS'],'reviewed_clause':'검토 조항','reason':'근거 확인','criterion_date':str(pms.today())}
    post(c,f"/complaints/{cp['id']}/reporting-review",body,409)
    post(c,f"/complaints/{cp['id']}/reporting-review",{**body,'fictional_review':True,'deadline':str(pms.today())},422)
    d=post(c,f"/complaints/{cp['id']}/reporting-review",{**body,'fictional_review':True})
    assert d['reporting_review']['deadline'] is None and d['reporting_review']['status']=='검토 필요'

def test_plan_before_action_waiting_quantity_period_and_change_gate(client):
    c,_=client;p,lot,e=setup(c);cp=complaint(c,p,'LOT-1');ca=capa(c,cp);ca=action(c,ca);a=ca['actions'][0]
    post(c,f"/capas/{ca['id']}/actions/{a['id']}/complete",{'note':'실행','evidence_ids':[e]},409)
    pl=plan(c,ca);complete(c,ca,a,e)
    post(c,f"/capas/{ca['id']}/plans",{'reviewer':'QA',**pl['definition']},409)
    before=dist(c,ca,lot,pl,'before',e);after=dist(c,ca,lot,pl,'after',e,None)
    r=evaluate(c,ca,pl,e,as_of=str(pms.today()),before_distribution_id=before['id'],after_distribution_id=after['id']).json()
    assert r['status']=='waiting' and any('수량' in x for x in r['snapshot']['waiting_reasons']) and any('미종료' in x for x in r['snapshot']['waiting_reasons'])
    change=prepare_name(c,p);post(c,f"/capas/{ca['id']}/change-links",{'change_id':change['id']})
    closed=post(c,f"/capas/{ca['id']}/close",{'confirmed':True,'reason':'종결'},409)
    assert any(x['id']==change['id'] for x in closed['detail']['blockers'])

def test_failed_effectiveness_rework_versioned_reassessment_and_idempotency(client):
    c,_=client;p,lot,e=setup(c);cp=complaint(c,p,'LOT-1');ca=action(c,capa(c,cp));pl=plan(c,ca);complete(c,ca,ca['actions'][0],e)
    complaint(c,p,'LOT-1',pms.today()+timedelta(days=1))
    b=dist(c,ca,lot,pl,'before',e);a=dist(c,ca,lot,pl,'after',e)
    kwargs={'before_distribution_id':b['id'],'after_distribution_id':a['id']}
    r=evaluate(c,ca,pl,e,**kwargs);assert r.status_code==201,r.text
    failed=r.json();assert failed['status']=='failed' and failed['snapshot']['cohorts']['after']['rate_per_1000']==1
    assert evaluate(c,ca,pl,e,**kwargs).json()==failed
    assert evaluate(c,ca,pl,e,as_of=str(pms.today()),**kwargs).status_code==409
    ca=c.get('/ivd/capas/'+ca['id']).json();assert len(ca['actions'])==2
    rework=next(x for x in ca['actions'] if x['trigger_evaluation_id']);pl2=plan(c,ca,11);complete(c,ca,rework,e)
    b2=dist(c,ca,lot,pl2,'before',e);a2=dist(c,ca,lot,pl2,'after',e)
    passed=evaluate(c,ca,pl2,e,'reeval',before_distribution_id=b2['id'],after_distribution_id=a2['id']).json();assert passed['status']=='passed'
    final=post(c,f"/capas/{ca['id']}/close",{'confirmed':True,'reason':'합성 관찰 완료'})
    assert [x['status'] for x in final['evaluations']]==['failed','passed'] and [x['version'] for x in final['plans']]==[1,2]
    assert evaluate(c,ca,pl,e,**kwargs).json()==failed
    exported=post(c,f"/complaints/{cp['id']}/exports",{},201)
    report=c.get('http://testserver'+exported['json_url']).json();assert report['capas'][0]['evaluations'][0]==failed
    assert '가상 제품 · 검토용 예시' in c.get('http://testserver'+exported['markdown_url']).text

def test_ai_summary_rejects_unconnected_ids_without_workflow_change(client,monkeypatch):
    c,_=client;p,lot,e=setup(c);cp=complaint(c,p,'LOT-1');before=c.get('/ivd/complaints/'+cp['id']).json()
    monkeypatch.setattr(pms,'summary_provider',lambda _: {'sentences':[{'text':'추정','evidence_ids':['unrelated']}]})
    assert c.post(f"/ivd/complaints/{cp['id']}/summary",json={'provider':'huggingface'}).status_code==422
    assert c.get('/ivd/complaints/'+cp['id']).json()==before
    monkeypatch.setattr(pms,'summary_provider',lambda _: {'sentences':[{'text':'등록 사실의 내부 검토용 요약','evidence_ids':[cp['id']]}]})
    result=c.post(f"/ivd/complaints/{cp['id']}/summary",json={'provider':'huggingface'})
    assert result.status_code==200 and result.json()['review_only'] is True
    assert c.post(f"/ivd/complaints/{cp['id']}/summary",json={'provider':'manual'}).json()['ai_used'] is False

def test_distribution_cohort_and_market_scope_are_validated(client):
    c,_=client;p,lot,e=setup(c);cp=complaint(c,p,'LOT-1');ca=action(c,capa(c,cp));pl=plan(c,ca)
    other=baseline(c,'COVID','KR');wrong=post(c,'/lots',{'product_id':other['product']['id'],'market':'KR','number':'OTHER','package_id':other['id']},201)
    post(c,f"/capas/{ca['id']}/distributions",{'lot_ids':[wrong['id']],'period_start':pl['definition']['after_start'],'period_end':pl['definition']['after_end'],'quantity':1000,'source':'다른 시장 원장','evidence_ids':[e]},422)
    complete(c,ca,ca['actions'][0],e)
    b=dist(c,ca,lot,pl,'before',e)
    # A valid same-product distribution still cannot supply a different period's denominator.
    assert evaluate(c,ca,pl,e,before_distribution_id=b['id'],after_distribution_id=b['id']).status_code==422
