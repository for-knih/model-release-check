import importlib
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend import db, main, evaluation
from backend.models import DATA, LocalAdapter

@pytest.fixture
def client(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    db.Base.metadata.create_all(engine)
    session = db.sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(main, 'Session', session)
    monkeypatch.setattr(evaluation, 'Session', session)
    monkeypatch.setattr(main, 'dispatch', lambda _: None)
    with TestClient(main.app) as c:
        yield c, session
    engine.dispose()

def request(c, **kwargs):
    ds=c.post('/datasets/sample').json()['id']
    return {'dataset_id': ds, 'mode': 'scenario', **kwargs}

def start(c, body, key='key'):
    return c.post('/runs', json=body, headers={'Idempotency-Key':key})

def test_csv_errors(client):
    c,_=client
    res=c.post('/datasets',files={'file':('bad.csv','case_id,text,expected_label\na,,배송\nb,문의,없는라벨\nb,중복,기타\n'.encode())})
    assert res.status_code==422
    assert [e['row'] for e in res.json()['detail']]==[2,3,4]

@pytest.mark.parametrize('content',[b'',b'case_id,text,expected_label\n',b'wrong,header\n',b'\xff'])
def test_invalid_csv(client,content):
    assert client[0].post('/datasets',files={'file':('x.csv',content)}).status_code==422

def test_idempotency_and_conflict(client):
    c,_=client;body=request(c)
    first=start(c,body)
    assert first.status_code==202
    assert start(c,body).json()['run_id']==first.json()['run_id']
    assert start(c,{**body,'mode':'local'}).status_code==409

def test_queue_failure_retry(client,monkeypatch):
    c,sessions=client;body=request(c)
    def fail(_):raise ConnectionError('Redis down')
    monkeypatch.setattr(main,'dispatch',fail)
    failed=start(c,body)
    assert failed.status_code==503
    run_id=failed.json()['detail']['run_id']
    with sessions() as s:assert not s.get(db.Run,run_id).dispatched
    calls=[]
    monkeypatch.setattr(main,'dispatch',calls.append)
    assert start(c,body).json()['run_id']==run_id
    assert start(c,body).json()['run_id']==run_id
    assert calls==[run_id]

def test_scenario_metrics_reviews_and_retry(client):
    c,sessions=client;run_id=start(c,request(c)).json()['run_id']
    assert c.post(f'/runs/{run_id}/reviews',json={'reviewer':'QA','decision':'hold','reason':'미완료'}).status_code==409
    evaluation.evaluate(run_id)
    result=c.get('/runs/'+run_id).json()['result']
    assert result['baseline']['accuracy']==.6
    assert result['candidate']['accuracy']==.85
    assert result['baseline']['classes']['환불']['recall']==1
    assert result['candidate']['classes']['환불']['recall']==.6
    assert result['recommendation']=='hold' and len(result['reasons'])==2
    assert sum(r['baseline']==r['expected_label'] and r['candidate']!=r['expected_label'] for r in result['cases'])==2
    evaluation.evaluate(run_id)
    with sessions() as s:assert s.scalar(select(func.count()).select_from(db.Prediction))==40
    assert c.post(f'/runs/{run_id}/reviews',json={'reviewer':'QA','decision':'hold','reason':' '}).status_code==422
    assert c.post(f'/runs/{run_id}/reviews',json={'reviewer':'QA','decision':'hold','reason':'환불 재현율 하락 확인'}).status_code==201
    assert len(c.get(f'/runs/{run_id}/reviews').json())==1
    assert c.get('/runs/'+run_id).json()['result']['recommendation']=='hold'

def test_partial_retry_and_failure(client,monkeypatch):
    c,sessions=client;run_id=start(c,request(c)).json()['run_id']
    original=evaluation.compare
    def fail(*_):raise RuntimeError('interruption')
    monkeypatch.setattr(evaluation,'compare',fail)
    with pytest.raises(RuntimeError):evaluation.evaluate(run_id)
    assert c.get('/runs/'+run_id).json()['status']=='failed'
    with sessions() as s:
        # Simulate a genuinely partial attempt; retry must fill the missing result.
        s.delete(s.scalar(select(db.Prediction)))
        s.commit()
    monkeypatch.setattr(evaluation,'compare',original)
    evaluation.evaluate(run_id)
    assert c.get('/runs/'+run_id).json()['status']=='succeeded'
    with sessions() as s:assert s.scalar(select(func.count()).select_from(db.Prediction))==40

def test_no_refund(client):
    c,_=client
    ds=c.post('/datasets',files={'file':('small.csv','case_id,text,expected_label\nx,배송 언제 와요,배송\n'.encode())}).json()['id']
    run_id=start(c,{'dataset_id':ds,'mode':'local'}).json()['run_id']
    evaluation.evaluate(run_id)
    result=c.get('/runs/'+run_id).json()['result']
    assert result['recommendation']=='hold'
    assert result['refund_evaluable'] is False
    assert result['candidate']['classes']['환불']=={'recall':None,'support':0}

def test_train_eval_separation():
    train=main.parse_csv((DATA/'train.csv').read_bytes())
    test=main.parse_csv((DATA/'evaluation.csv').read_bytes())
    assert not ({x['text'] for x in train}&{x['text'] for x in test})
    assert LocalAdapter().predict('환불 신청합니다') in main.LABELS

def test_scenario_rejects_custom_dataset(client):
    c,_=client
    ds=c.post('/datasets',files={'file':('custom.csv','case_id,text,expected_label\nx,안녕,기타\n'.encode())}).json()['id']
    assert start(c,{'dataset_id':ds,'mode':'scenario'}).status_code==422
