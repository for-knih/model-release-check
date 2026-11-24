"""Two virtual-product change flows over the running local HTTP API."""
import json
from pathlib import Path
import httpx

def main():
    output=Path('reports/ivd-changes');output.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url='http://127.0.0.1:8000/ivd',timeout=45) as c:
        def send(method,path,**kw):
            r=c.request(method,path,**kw);r.raise_for_status();return r.json()
        def post(path,body=None):return send('POST',path,json=body or {})
        def baseline(product,market):
            revisions=send('GET',f'/products/{product}/revisions');current=next(r for r in revisions['revisions'] if r['revision']==revisions['current_revision'])
            listed=send('GET',f'/packages?product_id={product}&market={market}')
            for row in listed:
                if row['status']!='internal_complete':continue
                p=send('GET','/packages/'+row['id'])
                if p['product_revision_id']==current['id'] and not any(q['family_id']==row['family_id'] and q['version']>row['version'] for q in listed):return p
            p=post('/packages',{'product_id':product,'market':market,'basis':'fictional' if market=='KR' else 'official'})
            material=send('GET',f'/products/{product}/materials');perf=sorted([e for e in material['evidence'] if e['key']=='performance'],key=lambda x:x['revision'])
            if not perf:perf=[post(f'/products/{product}/evidence',{'key':'performance','title':'가상 성능 자료 메타데이터','summary':'실제 성능값 없음. 시연을 위한 등록 자료 위치만 표시','citation':'가상://성능 자료 §1'})]
            post(f"/packages/{p['id']}/regulatory-review",{'reviewer':'시연 기준 검토자','classification':'가상 분류 검토 예시','submission_route':'가상 내부 검토 경로','rationale':'가상 메타데이터 및 등록 근거 확인; 실제 규제 확정 아님','source_ids':['EU-IVDR' if market=='EU' else 'KR-MFDS'],'fictional_review':True})
            for m in p['mappings']:
                send('PATCH',f"/packages/{p['id']}/requirements/{m['key']}",json={'document_id':m['document']['id'],'evidence_ids':[perf[-1]['id']] if m['section']=='performance' else [e['id'] for e in m['evidence']],'applicability':'applicable','state':'satisfied','reviewer':'시연 기준 검토자','rationale':'등록된 합성 문서·메타데이터의 검토 범위 확인'})
            return post(f"/packages/{p['id']}/complete",{'reviewer':'시연 기준 검토자'})
        def request(packages,fields=None,replacements=None):
            p=packages[0]
            return post('/changes',{'product_id':p['product']['id'],'base_revision_id':p['product_revision_id'],'changes':fields or [],'evidence_replacements':replacements or {},'baseline_packages':{p['market']:p['id'] for p in packages},'reason':'가상 제품 · 검토용 예시 변경 요청','requester':'시연 요청자'})
        def assess(r):
            d=post(f"/changes/{r['id']}/assess",{'reviewer':'영향평가자'});post(f"/changes/{r['id']}/start-review",{'reviewer':'재검토자'});return d
        def judge_market(id,market):return post(f'/changes/{id}/markets/{market}/decision',{'reviewer':market+' 시장 검토자','reason':market+' 공식 근거 메타데이터와 변경 후보를 확인한 가상 판단','source_ids':['EU-IVDR' if market=='EU' else 'KR-MFDS'],'legal_procedure':market+' 가상 변경 절차 검토. 실제 제출 여부는 규제 검토 필요','submission_required':None,'fictional_review':True})
        def export(id,name):
            artifact=post(f'/changes/{id}/exports')
            for kind,ext in [('json','json'),('markdown','md')]:
                r=c.get('http://127.0.0.1:8000'+artifact[kind+'_url']);r.raise_for_status();(output/(name+'.'+ext)).write_text(r.text,encoding='utf-8')
            return artifact
        post('/sample');post('/change-rules/sample')
        hiv=baseline('IVD-HIV-DEMO','EU');old=next(m for m in hiv['mappings'] if m['section']=='performance')['evidence'][0]
        all_evidence=send('GET','/products/IVD-HIV-DEMO/materials')['evidence'];latest=max((e for e in all_evidence if e['key']==old['key']),key=lambda e:e['revision'])
        new=post('/products/IVD-HIV-DEMO/evidence',{'key':old['key'],'title':'가상 성능 자료 위치 개정','summary':'합성 증빙의 등록 위치·문서 식별자만 개정. 실제 성능 수치 추가 없음','citation':'가상://성능 자료 개정 §1','previous_id':latest['id']})
        h=request([hiv],replacements={old['id']:new['id']});impact=assess(h)
        assert len(impact['items'])==1 and impact['items'][0]['section']=='performance'
        blocked=c.post(f"/changes/{h['id']}/approve",json={'reviewer':'최종 검토자'});assert blocked.status_code==409
        work=post(f"/changes/{h['id']}/markets/EU/requests",{'section':'performance','reason':'교체 증빙 인용 위치의 추가 확인','owner':'자료 담당자','due_date':'2026-12-01','reviewer':'재검토자'})
        wm=next(m for m in send('GET','/packages/'+work['work_package_id'])['mappings'] if m['section']=='performance')
        send('PATCH',f"/packages/{work['work_package_id']}/requirements/{wm['key']}",json={'document_id':wm['document']['id'],'evidence_ids':[new['id']],'applicability':'applicable','state':'satisfied','reviewer':'자료 검토자','rationale':'작업용 복사본에서 제안 증빙 메타데이터 확인'})
        post(f"/requests/{work['id']}/answer",{'reviewer':'자료 작성자','answer':'새 합성 증빙의 인용 위치와 개정본 식별자를 확인했습니다. 성능값은 변경하지 않았습니다.','evidence_ids':[new['id']]})
        post(f"/requests/{work['id']}/start-review",{'reviewer':'자료 검토자'});post(f"/requests/{work['id']}/close",{'reviewer':'자료 검토자','confirmed':True,'reason':'등록 위치와 인용 개정본 확인'})
        post(f"/changes/{h['id']}/items/{impact['items'][0]['id']}/decision",{'reviewer':'재검토자','choice':'revise','reason':'참조된 합성 증빙의 개정본으로 교체 필요','evidence_replacements':{old['id']:new['id']}})
        judge_market(h['id'],'EU')
        approved_h=post(f"/changes/{h['id']}/approve",{'reviewer':'최종 검토자'})
        assert post(f"/changes/{h['id']}/approve",{'reviewer':'최종 검토자'})==approved_h
        assert send('GET','/packages/'+hiv['id'])==hiv
        h_export=export(h['id'],'hiv-eu-change')
        kr=baseline('IVD-COVID-DEMO','KR');eu=baseline('IVD-COVID-DEMO','EU')
        old_name=kr['product']['name'];revision=send('GET','/products/IVD-COVID-DEMO/revisions')['current_revision'];new_name='COVID-19 항원 검사 가상 제품 · 명칭 r'+str(revision+1)
        covid=request([kr,eu],fields=[{'field':'name','before':old_name,'after':new_name}]);ci=assess(covid)
        assert {(i['market'],i['section']) for i in ci['items']}=={(m,section) for m in ['KR','EU'] for section in ['overview','labeling']}
        first=judge_market(covid['id'],'KR');assert next(m for m in first['markets'] if m['market']=='EU')['judgment'] is None
        for item in ci['items']:
            doc=item['document'];content=doc['content'].replace(old_name,new_name)
            if new_name not in content:content+='\n가상 제품명 메타데이터: '+new_name
            revised=post('/products/IVD-COVID-DEMO/documents',{'section':item['section'],'content':content,'citation':doc['citation']+'; 제품명 변경 요청 '+covid['id']})
            post(f"/changes/{covid['id']}/items/{item['id']}/decision",{'reviewer':item['market']+' 문서 검토자','choice':'revise','reason':'가상 제품명 변경 부분만 새 문서 개정본에 반영','document_id':revised['id']})
        judge_market(covid['id'],'EU')
        approved_c=post(f"/changes/{covid['id']}/approve",{'reviewer':'최종 검토자'})
        assert post(f"/changes/{covid['id']}/approve",{'reviewer':'최종 검토자'})==approved_c
        assert send('GET','/packages/'+kr['id'])==kr and send('GET','/packages/'+eu['id'])==eu
        c_export=export(covid['id'],'covid-name-change')
        evidence={'hiv_change_id':h['id'],'covid_change_id':covid['id'],'hiv_candidate_count':len(impact['items']),'covid_candidate_count':len(ci['items']),
            'unresolved_completion_http':blocked.status_code,'old_packages_preserved':True,'market_judgments_independent':True,'retransmission_same_outcome':True,
            'hiv_result':approved_h,'covid_result':approved_c,'hiv_export':h_export,'covid_export':c_export,'hiv_url':f"http://localhost:8080/?ivd_changes=1&change={h['id']}",'covid_url':f"http://localhost:8080/?ivd_changes=1&change={covid['id']}"}
        (output/'demo.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:evidence[k] for k in ['hiv_url','covid_url','hiv_candidate_count','covid_candidate_count','unresolved_completion_http','old_packages_preserved','retransmission_same_outcome']},ensure_ascii=False))

if __name__=='__main__':main()
