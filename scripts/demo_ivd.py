"""Actual HTTP demo using virtual metadata, no external AI key or clinical claims."""
import json
from pathlib import Path
import httpx

def main():
    out=Path('reports/ivd');out.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url='http://127.0.0.1:8000/ivd',timeout=30) as c:
        def send(method,path,**kwargs):
            r=c.request(method,path,**kwargs);r.raise_for_status();return r.json()
        def export(p,name):
            a=send('POST',f"/packages/{p['id']}/exports")
            for kind,ext in [('json','json'),('markdown','md')]:
                r=c.get('http://127.0.0.1:8000'+a[kind+'_url']);r.raise_for_status();(out/(name+'.'+ext)).write_text(r.text,encoding='utf-8')
            return a
        send('POST','/sample')
        hiv=send('POST','/packages',json={'product_id':'IVD-HIV-DEMO','market':'EU'})
        covid=send('POST','/packages',json={'product_id':'IVD-COVID-DEMO','market':'KR','basis':'fictional'})
        hivkr=send('POST','/packages',json={'product_id':'IVD-HIV-DEMO','market':'KR','basis':'fictional'})
        kr_before=send('GET','/packages/'+hivkr['id']);covid_before=send('GET','/packages/'+covid['id'])
        missing=next(m for m in hiv['mappings'] if m['section']=='performance')
        # A repeated demo may already have material revisions registered. Mark the
        # virtual perf item as missing explicitly in this new draft for the scenario.
        if missing['evidence']:
            send('PATCH',f"/packages/{hiv['id']}/requirements/{missing['key']}",json={'document_id':missing['document']['id'],'evidence_ids':[],'state':'missing','applicability':'unconfirmed','reviewer':'시연 검토자','rationale':'가상 누락 시나리오; 이번 패키지에는 자료 미연결'})
        req=send('POST',f"/packages/{hiv['id']}/requests",json={'requirement_key':missing['key'],'reason':'성능평가 자료 메타데이터와 문서 개정본 보완 필요','owner':'자료 담당자','due_date':'2026-12-01','reviewer':'시연 검토자'})
        old=send('GET','/packages/'+hiv['id']);draft_export=export(old,'hiv-eu-v1-draft')
        perf=send('GET','/products/IVD-HIV-DEMO/materials')
        prior=sorted([e for e in perf['evidence'] if e['key']=='performance'],key=lambda e:e['revision'])
        e=send('POST','/products/IVD-HIV-DEMO/evidence',json={'key':'performance','title':'가상 성능평가 자료 메타데이터','summary':'가상 등록 파일과 인용 위치만 확인. 실제 성능 수치 없음.','citation':'가상://HIV/performance/report §1','previous_id':prior[-1]['id'] if prior else None})
        d=send('POST','/products/IVD-HIV-DEMO/documents',json={'section':'performance','content':'가상 제품 · 검토용 예시. 등록된 성능평가 자료 메타데이터와 인용 위치를 목록화했습니다. 실제 성능 수치는 제공되지 않았습니다.','citation':e['citation']})
        v2=send('POST',f"/packages/{hiv['id']}/versions",json={'reviewer':'시연 검토자','documents':{'performance':d['id']}})
        assert send('GET','/packages/'+hiv['id'])==old
        assert next(m for m in v2['mappings'] if m['section']=='performance')['state_label']=='재검토 필요'
        send('POST',f"/packages/{v2['id']}/regulatory-review",json={'reviewer':'시연 검토자','classification':'가상 분류 검토 예시','submission_route':'가상 내부 문서 검토 경로','rationale':'공식 IVDR 번호·제목과 제품 가상 메타데이터를 대조한 내부 검토 예시. 실제 등급이나 제출 경로 확정 아님','source_ids':['EU-IVDR'],'fictional_review':True})
        for m in v2['mappings']:
            ids=[e['id']] if m['section']=='performance' else [x['id'] for x in m['evidence']]
            send('PATCH',f"/packages/{v2['id']}/requirements/{m['key']}",json={'document_id':m['document']['id'],'evidence_ids':ids,'state':'satisfied','applicability':'applicable','reviewer':'시연 검토자','rationale':'가상 제품 내부 검토: 등록 메타데이터·인용 범위 및 문서 개정본을 확인. 규제 적합성 확정 아님'})
        v2=send('GET','/packages/'+v2['id']);r=v2['requests'][0]
        blocked=c.post(f"/packages/{v2['id']}/complete",json={'reviewer':'시연 검토자'});assert blocked.status_code==409
        manual=send('POST',f"/requests/{r['id']}/draft",json={'provider':'manual'});assert not manual['ai_used']
        send('POST',f"/requests/{r['id']}/answer",json={'reviewer':'답변 작성자','answer':'성능평가 자료 메타데이터와 문서 개정본을 연결했습니다. 등록 인용 위치만 요약했으며 실제 성능 수치를 추가하지 않았습니다.','evidence_ids':[e['id']]})
        send('POST',f"/requests/{r['id']}/start-review",json={'reviewer':'재검토자'})
        send('POST',f"/requests/{r['id']}/close",json={'reviewer':'재검토자','confirmed':True,'reason':'답변·문서 ID·증빙 개정본과 인용 위치를 확인한 가상 검토 종결'})
        complete=send('POST',f"/packages/{v2['id']}/complete",json={'reviewer':'재검토자'})
        final=export(complete,'hiv-eu-v2-reviewed');export(covid,'covid-kr-v1-draft');export(hivkr,'hiv-kr-v1-draft')
        assert send('GET','/packages/'+hivkr['id'])==kr_before and send('GET','/packages/'+covid['id'])==covid_before
        diff=send('GET',f"/packages/{hiv['id']}/compare/{v2['id']}")
        (out/'source-verification.json').write_text(json.dumps(send('GET','/sources'),ensure_ascii=False,indent=2),encoding='utf-8')
        evidence={'hiv_eu_v1':hiv['id'],'hiv_eu_v2':v2['id'],'covid_kr':covid['id'],'hiv_kr':hivkr['id'],'missing_requirement':missing['key'],'evidence_revision':e,'open_request_completion_rejected':blocked.status_code,'final_status':complete['status'],'regulatory_status':complete['regulatory_status'],'old_package_preserved':True,'product_market_isolation':True,'diff':diff,'manual_reply':manual,'draft_export':draft_export,'final_export':final,'url':f"http://localhost:8080/?ivd=1&package={v2['id']}"}
        (out/'demo.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:evidence[k] for k in ['url','final_status','regulatory_status','open_request_completion_rejected','old_package_preserved','product_market_isolation']},ensure_ascii=False))

if __name__=='__main__':main()
