import copy
import pytest
from backend import ivd
from test_platform import client

def make(c,product='HIV',market='EU',basis='official'):
    assert c.post('/ivd/sample').status_code==201
    r=c.post('/ivd/packages',json={'product_id':f'IVD-{product}-DEMO','market':market,'basis':basis})
    assert r.status_code==201,r.text
    return r.json()
def reg(c,p,fictional=True):
    return c.post(f"/ivd/packages/{p['id']}/regulatory-review",json={'reviewer':'가상 검토자','classification':'가상 분류 검토 예시','submission_route':'가상 내부 검토 경로','rationale':'가상 제품 자료와 출처를 확인한 시연용 판단; 실제 등급·경로 확정 아님','source_ids':['EU-IVDR' if p['market']=='EU' else 'KR-MFDS'],'fictional_review':fictional})
def review(c,p,m,state='satisfied',ids=None):
    return c.patch(f"/ivd/packages/{p['id']}/requirements/{m['key']}",json={'document_id':m['document']['id'],'evidence_ids':[e['id'] for e in m['evidence']] if ids is None else ids,'applicability':'not_applicable' if state=='not_applicable' else 'applicable','state':state,'reviewer':'검토자','rationale':'등록된 가상 메타데이터와 적용 판단 근거 검토'})
def ev(c,product='HIV',key='performance',previous=None):
    r=c.post(f'/ivd/products/IVD-{product}-DEMO/evidence',json={'key':key,'title':'가상 자료 메타데이터','summary':'실제 성능 수치 미제공. 검토용 파일 메타데이터 등록','citation':'가상://demo/report §1','previous_id':previous})
    assert r.status_code==201,r.text
    return r.json()

def test_unverified_source_never_auto_confirmed(client):
    c,_=client;p=make(c,'COVID','KR')
    assert p['regulatory_status']=='규제 검토 필요' and p['regulatory_review'] is None
    assert reg(c,p,False).status_code==409
    assert review(c,p,p['mappings'][0]).status_code==409
    assert c.post(f"/ivd/packages/{p['id']}/complete",json={'reviewer':'QA'}).status_code==409
    assert c.get('/ivd/sources').json()['sources']['EU-IVDR']['number']=='Regulation (EU) 2017/746'

def test_cross_product_documents_evidence_rejected(client):
    c,_=client;p=make(c);covid=c.get('/ivd/products/IVD-COVID-DEMO/materials').json();m=p['mappings'][0]
    assert review(c,p,m,ids=[covid['evidence'][0]['id']]).status_code==422
    body={'document_id':covid['documents'][0]['id'],'evidence_ids':[],'reviewer':'QA','rationale':'문서 검증'}
    assert c.patch(f"/ivd/packages/{p['id']}/requirements/{m['key']}",json=body).status_code==422
    assert c.post(f"/ivd/packages/{p['id']}/versions",json={'reviewer':'QA','documents':{'overview':covid['documents'][0]['id']}}).status_code==422

def test_not_applicable_requires_reason(client):
    c,_=client;p=make(c);m=p['mappings'][0]
    assert review(c,p,m,'not_applicable',[]).status_code==200
    body={'document_id':m['document']['id'],'applicability':'not_applicable','state':'not_applicable','reviewer':'QA','rationale':' '}
    assert c.patch(f"/ivd/packages/{p['id']}/requirements/{m['key']}",json=body).status_code==422

def test_full_supplement_cycle_and_open_request_blocks_completion(client,monkeypatch):
    c,_=client;p=make(c);assert reg(c,p).status_code==200
    for m in p['mappings']:
        if m['section']!='performance':assert review(c,p,m).status_code==200
    missing=next(m for m in p['mappings'] if m['section']=='performance')
    request=c.post(f"/ivd/packages/{p['id']}/requests",json={'requirement_key':missing['key'],'reason':'성능 자료 메타데이터 누락','owner':'자료 담당자','due_date':'2026-12-01','reviewer':'QA'}).json()
    e=ev(c)
    assert review(c,p,missing,ids=[e['id']]).status_code==200
    blocked=c.post(f"/ivd/packages/{p['id']}/complete",json={'reviewer':'QA'})
    assert blocked.status_code==409 and any('보완' in x for x in blocked.json()['detail']['unresolved'])
    assert c.post(f"/ivd/requests/{request['id']}/close",json={'reviewer':'QA','confirmed':True,'reason':'확인'}).status_code==409
    manual=c.post(f"/ivd/requests/{request['id']}/draft",json={'provider':'manual'}).json();assert not manual['ai_used'] and manual['draft'] is None
    assert c.post(f"/ivd/requests/{request['id']}/answer",json={'reviewer':'작성자','answer':'등록 메타데이터에 근거한 수동 답변','evidence_ids':[e['id']]}).json()['requests'][0]['status']=='review_pending'
    assert c.post(f"/ivd/requests/{request['id']}/start-review",json={'reviewer':'QA'}).status_code==200
    assert c.post(f"/ivd/requests/{request['id']}/close",json={'reviewer':'QA','confirmed':True,'reason':'답변과 연결 개정본 확인'}).status_code==200
    done=c.post(f"/ivd/packages/{p['id']}/complete",json={'reviewer':'QA'});assert done.status_code==200
    assert done.json()['regulatory_status']=='규제 검토 필요' # fictional review never establishes regulatory approval
    monkeypatch.delenv('HF_TOKEN',raising=False)
    artifact=c.post(f"/ivd/packages/{p['id']}/exports").json()
    exported=c.get(artifact['json_url']).json();md=c.get(artifact['markdown_url']).text
    assert '가상 제품 · 검토용 예시' in md and 'EU' in md and '2017/746' in md
    assert exported['status']=='internal_complete' and exported['requests'][0]['status']=='closed'
    assert c.patch(f"/ivd/packages/{p['id']}/requirements/{missing['key']}",json={}).status_code==422

def test_revision_preserves_previous_package_and_market_independence(client):
    c,_=client;p=make(c);kr=make(c,market='KR',basis='fictional');m=p['mappings'][0]
    assert review(c,p,m).status_code==200
    before=c.get('/ivd/packages/'+p['id']).json();kr_before=c.get('/ivd/packages/'+kr['id']).json()
    old=m['evidence'][0];new=ev(c,key=old['key'],previous=old['id'])
    doc=c.post('/ivd/products/IVD-HIV-DEMO/documents',json={'section':m['section'],'content':'등록 자료 변경 메타데이터만 요약','citation':'가상 문서 §2'}).json()
    newer=c.post(f"/ivd/packages/{p['id']}/versions",json={'reviewer':'QA','evidence_replacements':{old['id']:new['id']},'documents':{m['section']:doc['id']}})
    assert newer.status_code==201,newer.text
    v2=newer.json();changed=next(x for x in v2['mappings'] if x['key']==m['key'])
    assert changed['state_label']=='재검토 필요' and changed['evidence'][0]['revision']==2
    assert c.get('/ivd/packages/'+p['id']).json()==before
    assert c.get('/ivd/packages/'+kr['id']).json()==kr_before
    diff=c.get(f"/ivd/packages/{p['id']}/compare/{v2['id']}").json()
    assert diff['changes'][0]['document_before']!=diff['changes'][0]['document_after']
    assert c.get(f"/ivd/packages/{p['id']}/compare/{kr['id']}").status_code==422
    assert review(c,p,m).status_code==409 # branched parent is frozen

def test_draft_export_frozen_and_without_key(client,monkeypatch):
    c,_=client;p=make(c,'COVID','KR','fictional');monkeypatch.delenv('HF_TOKEN',raising=False)
    artifact=c.post(f"/ivd/packages/{p['id']}/exports").json();snapshot=c.get(artifact['json_url']).json()
    assert snapshot['status']=='draft' and snapshot['unresolved'] and snapshot['unverified_sources']
    assert '가상 검토 기준' in c.get(artifact['markdown_url']).text
    review(c,p,p['mappings'][0],'not_applicable',[])
    assert c.get(artifact['json_url']).json()==snapshot

@pytest.mark.parametrize('bad',[False,True])
def test_ai_sentence_citations_package_scope(client,monkeypatch,bad):
    c,_=client;p=make(c);m=p['mappings'][0]
    r=c.post(f"/ivd/packages/{p['id']}/requests",json={'section':m['section'],'reason':'자료 보완','owner':'작성자','reviewer':'QA','due_date':'2026-12-01'}).json()
    before=c.get('/ivd/packages/'+p['id']).json()
    monkeypatch.setattr(ivd,'ai_provider',lambda _: {'sentences':[{'text':'등록된 문서 메타데이터를 확인했습니다','citations':[{'kind':'document','id':'foreign-id' if bad else m['document']['id']}]}]})
    response=c.post(f"/ivd/requests/{r['id']}/draft",json={'provider':'huggingface'})
    assert response.status_code==(422 if bad else 200)
    assert c.get('/ivd/packages/'+p['id']).json()==before

def test_edited_ai_reply_revalidated_on_save(client):
    c,_=client;p=make(c);m=p['mappings'][0]
    r=c.post(f"/ivd/packages/{p['id']}/requests",json={'section':m['section'],'reason':'수정 초안 검증','owner':'작성자','reviewer':'QA','due_date':'2026-12-01'}).json()
    draft={'sentences':[{'text':'검토자가 수정한 문장','citations':[{'kind':'document','id':m['document']['id']}]}]}
    body={'reviewer':'작성자','answer':'다른 문장','draft':draft,'evidence_ids':[]}
    assert c.post(f"/ivd/requests/{r['id']}/answer",json=body).status_code==422
    body['answer']='검토자가 수정한 문장'
    assert c.post(f"/ivd/requests/{r['id']}/answer",json=body).status_code==200
    body['draft']['sentences'][0]['citations'][0]['id']='outside-package'
    assert c.post(f"/ivd/requests/{r['id']}/answer",json=body).status_code==422
