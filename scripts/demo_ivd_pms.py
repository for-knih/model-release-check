"""HTTP-only synthetic PMS demonstration; no external AI or reporting."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
from pathlib import Path
import json
import httpx
class Clock:
    @staticmethod
    def today():return datetime.now(ZoneInfo('Asia/Seoul')).date()
pms=Clock()

def baseline(c,product,market):
    pid='IVD-'+product+'-DEMO'
    current=c.get('/ivd/products/'+pid+'/revisions').json()['current_revision']
    rows=c.get('/ivd/packages',params={'product_id':pid,'market':market}).json()
    for row in sorted(rows,key=lambda r:r['version'],reverse=True):
        if any(q['family_id']==row['family_id'] and q['version']>row['version'] for q in rows):continue
        p=c.get('/ivd/packages/'+row['id']).json()
        if p['status']=='internal_complete' and p['product_revision']==current:return p
    p=c.post('/ivd/packages',json={'product_id':pid,'market':market,'basis':'fictional' if market=='KR' else 'official'}).json()
    proof=c.get('/ivd/products/'+pid+'/materials').json()['evidence'][0]['id']
    post(c,'/packages/'+p['id']+'/regulatory-review',{'classification':'가상 분류','submission_route':'가상 경로','rationale':'합성 자료의 내부 시연','source_ids':['EU-IVDR' if market=='EU' else 'KR-MFDS'],'fictional_review':True})
    for m in p['mappings']:
        r=c.patch('/ivd/packages/'+p['id']+'/requirements/'+m['key'],json={'document_id':m['document']['id'],'evidence_ids':[proof] if m['section']=='performance' else [e['id'] for e in m['evidence']],'applicability':'applicable','state':'satisfied','reviewer':'QA','rationale':'합성 메타데이터 확인'});r.raise_for_status()
    return post(c,'/packages/'+p['id']+'/complete',{})
def post(c,path,body,code=200):
    r=c.post('/ivd'+path,json=body if path=='/changes' else {'reviewer':'QA',**body});assert r.status_code==code,r.text
    return r.json()

def setup(c,product='HIV',market='EU'):
    p=baseline(c,product,market);pid=p['product']['id']
    lot=post(c,'/lots',{'product_id':pid,'market':market,'number':'LOT-'+uuid4().hex[:8],'package_id':p['id']},201)
    e=c.post(f'/ivd/products/{pid}/evidence',json={'key':'pms-'+uuid4().hex[:8],'title':'가상 조사 증빙','summary':'가상 제품 · 검토용 예시','citation':'가상://조사'}).json()['id']
    return p,lot,e

def complaint(c,p,lot=None,day=None):
    return post(c,'/complaints',{'product_id':p['product']['id'],'market':p['market'],'lot_number':lot,'received_on':str(day or pms.today()-timedelta(days=2)),'problem_type':'missing_lot_label' if 'COVID' in p['product']['id'] else 'outdated_ifu','description':'가상 외부 상자 로트 표기 누락' if 'COVID' in p['product']['id'] else '가상 이전 설명서 동봉','observed_facts':'합성 사진 메타데이터','owner':'조사자','due_date':str(pms.today()+timedelta(days=30)),'synthetic':True},201)

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

def main():
    output=Path('reports/ivd-pms');output.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=45) as c:
        c.post('/ivd/sample').raise_for_status()
        def export(cp,name):
            x=post(c,f"/complaints/{cp['id']}/exports",{},201)
            for key,ext in [('json','json'),('markdown','md')]:
                r=c.get(x[key+'_url']);r.raise_for_status();(output/(name+'.'+ext)).write_text(r.text,encoding='utf-8')
            return x
        def actual_plan(ca,lot,start=0):
            t=pms.today()
            return post(c,f"/capas/{ca['id']}/plans",{'before_start':str(t-timedelta(days=10)),'before_end':str(t-timedelta(days=1)),'after_start':str(t+timedelta(days=start)),'after_end':str(t+timedelta(days=start+10)),'before_lot_numbers':[lot['number']],'after_lot_numbers':[lot['number']],'data_source':'가상 제품 · 검토용 예시 합성 원장','max_after_rate':0.5},201)
        p,lot,e=setup(c);h=complaint(c,p)
        h=post(c,f"/complaints/{h['id']}/confirm-lot",{'lot_id':lot['id'],'reason':'합성 로트 원장과 포장 사진을 대조'})
        h=post(c,f"/complaints/{h['id']}/investigation",{'hypothesis':'포장 작업의 설명서 개정 확인 누락 가능성','confirmed_cause':'합성 조사 기록에서 구개정 설명서 구분 누락 확인','evidence_ids':[e]})
        ca=action(c,capa(c,h))
        ca=post(c,f"/capas/{ca['id']}/actions",{'kind':'immediate','description':'가상 대상 포장의 설명서 개정 확인·분리','owner':'포장 담당자','due_date':str(pms.today()+timedelta(days=2))},201)
        pl=actual_plan(ca,lot)
        for act in ca['actions']:complete(c,ca,act,e)
        # A labeling-only metadata change uses the existing impact and revision workflow.
        r=c.post('/ivd/change-rules',json={'field':'labeling_revision_note','market':'EU','section':'labeling','version':1,'reason':'설명서 개정 확인 기록과 표시사항 섹션 연결'});r.raise_for_status()
        revisions=c.get('/ivd/products/IVD-HIV-DEMO/revisions').json()['revisions'];rev=next(x for x in revisions if x['id']==p['product_revision_id'])
        before=rev['data']['metadata'].get('labeling_revision_note')
        change=post(c,'/changes',{'product_id':p['product']['id'],'base_revision_id':p['product_revision_id'],'changes':[{'field':'labeling_revision_note','before':before,'after':'가상 설명서 확인 기록 '+uuid4().hex[:6]}],'baseline_packages':{'EU':p['id']},'reason':'이전 설명서 동봉 CAPA','requester':'CAPA 담당자'},201)
        post(c,f"/capas/{ca['id']}/change-links",{'change_id':change['id']})
        blocked=post(c,f"/capas/{ca['id']}/close",{'confirmed':True,'reason':'미완료 확인'},409)
        waiting=evaluate(c,ca,pl,e,'waiting',as_of=str(pms.today())).json();assert waiting['status']=='waiting'
        impact=post(c,f"/changes/{change['id']}/assess",{});post(c,f"/changes/{change['id']}/start-review",{})
        assert len(impact['items'])==1
        item=impact['items'][0];old_doc=item['document']['id']
        doc=c.post('/ivd/products/IVD-HIV-DEMO/documents',json={'section':'labeling','content':'가상 제품 · 검토용 예시. 설명서 개정본 식별 확인을 위한 합성 초안. 실제 표시·성능 지시가 아님.','citation':'가상://CAPA 설명서 개정'}).json()
        post(c,f"/changes/{change['id']}/items/{item['id']}/decision",{'choice':'revise','reason':'포장 개정본 식별 기록 반영','document_id':doc['id']})
        post(c,f"/changes/{change['id']}/markets/EU/decision",{'reason':'가상 내부 검토','source_ids':['EU-IVDR'],'legal_procedure':'실제 규제 절차는 검토 필요','submission_required':None,'fictional_review':True})
        final=post(c,f"/changes/{change['id']}/approve",{})
        effect_e=c.post('/ivd/products/IVD-HIV-DEMO/evidence',json={'key':'effect-'+uuid4().hex[:8],'title':'가상 조치 후 관찰 증빙','summary':'가상 제품 · 검토용 예시. 합성 유통·관찰 원장; 실행 증빙과 별도','citation':'가상://조치 후 효과성 관찰'}).json()['id']
        b=dist(c,ca,lot,pl,'before',effect_e);a=dist(c,ca,lot,pl,'after',effect_e)
        passed=evaluate(c,ca,pl,effect_e,'finished',before_distribution_id=b['id'],after_distribution_id=a['id']).json();assert passed['status']=='passed'
        ca=post(c,f"/capas/{ca['id']}/close",{'confirmed':True,'reason':'합성 유통·관찰 증빙에서 기준 충족'})
        saved=c.get('/ivd/complaints/'+h['id']).json();assert next(m for m in saved['lot']['snapshot']['mappings'] if m['section']=='labeling')['document']['id']==old_doc
        assert old_doc!=doc['id'];h_export=export(h,'hiv-outdated-ifu')
        p2,l2,e2=setup(c,'COVID','KR');root=complaint(c,p2,l2['number']);dup=complaint(c,p2,l2['number'])
        dup=post(c,f"/complaints/{dup['id']}/duplicate",{'representative_id':root['id'],'reason':'동일 상자 사진·로트·사건 확인'})
        # This COVID flow uses the missing-lot-label type, including all subsequent cohorts.
        assert dup['related']['raw_receipts']==2 and dup['related']['distinct_incidents']==1
        ca2=action(c,capa(c,root));pl1=actual_plan(ca2,l2);complete(c,ca2,ca2['actions'][0],e2)
        complaint(c,p2,l2['number'],pms.today()+timedelta(days=1))
        b1=dist(c,ca2,l2,pl1,'before',e2);a1=dist(c,ca2,l2,pl1,'after',e2)
        failed=evaluate(c,ca2,pl1,e2,'failure',before_distribution_id=b1['id'],after_distribution_id=a1['id']).json();assert failed['status']=='failed'
        ca2=c.get('/ivd/capas/'+ca2['id']).json();rw=next(a for a in ca2['actions'] if a['trigger_evaluation_id'])
        pl2=actual_plan(ca2,l2,11);complete(c,ca2,rw,e2)
        b2=dist(c,ca2,l2,pl2,'before',e2);a2=dist(c,ca2,l2,pl2,'after',e2)
        kw={'before_distribution_id':b2['id'],'after_distribution_id':a2['id']}
        success=evaluate(c,ca2,pl2,e2,'retry',**kw).json();assert success['status']=='passed'
        assert evaluate(c,ca2,pl2,e2,'retry',**kw).json()==success
        ca2=post(c,f"/capas/{ca2['id']}/close",{'confirmed':True,'reason':'재조치 후 합성 관찰 기간 기준 충족'})
        c_export=export(root,'covid-missing-label')
        result={'watermark':'가상 제품 · 검토용 예시','hiv':{'complaint_id':h['id'],'capa_id':ca['id'],'change_id':change['id'],'waiting':waiting['status'],'final':passed,'old_document_id':old_doc,'final_document_id':doc['id'],'old_lot_preserved':True,'export':h_export},'covid':{'complaint_id':root['id'],'capa_id':ca2['id'],'raw_receipts':2,'distinct_incidents':1,'evaluations':[failed,success],'plans':[pl1,pl2],'retry_same_id':True,'export':c_export}}
        (output/'demo.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'hiv':h['id'],'covid':root['id'],'hiv_status':passed['status'],'covid_history':[failed['status'],success['status']],'output':str(output)},ensure_ascii=False))

if __name__=='__main__':main()
