"""Real HTTP trace: requirement failure -> regression links -> repaired scenario -> review/export."""
import json
from pathlib import Path
import httpx
from scripts.pr_check import run_check,markdown

REF={'identifier':'REQ-REFUND-001','version':1}

def main():
    output=Path('reports/traceability');output.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as c:
        def send(method,path,**kwargs):
            r=c.request(method,path,**kwargs);r.raise_for_status();return r.json()
        requirement=send('POST','/requirements/sample')
        dataset=send('POST','/datasets/sample')
        reports={}
        for variant in ['original','repaired']:
            if variant=='repaired':
                source_id=reports['original']['run_id']
                links=send('POST',f'/runs/{source_id}/regression-links',json={'target_dataset_id':dataset['id'],'case_ids':['eval-008','eval-009','eval-008']})
                assert links['added_cases']==0
            body={'dataset_id':dataset['id'],'mode':'scenario','scenario_variant':variant,'commit_sha':'scenario-'+variant+'-demo','requirements':[REF]}
            report=run_check(c,body)
            assert report['exit_code']==(1 if variant=='original' else 0),report
            reports[variant]=report
            (output/f'{variant}-pr.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            (output/f'{variant}-pr.md').write_text(markdown(report),encoding='utf-8')
        initial,candidate=reports['original']['run_id'],reports['repaired']['run_id']
        old=send('GET','/runs/'+initial)
        failure=send('POST','/releases',json={'name':'최초 위반 검토','candidate_run_id':initial,'requirements':[REF]})
        blocked=c.post(f"/releases/{failure['id']}/reviews",json={'reviewer':'시연 검토자','decision':'approve','reason':'제한 검증'})
        assert blocked.status_code==409
        send('POST',f"/releases/{failure['id']}/reviews",json={'reviewer':'시연 검토자','decision':'hold','reason':'환불 재현율 60%, 최소 85% 및 최대 하락 5%p 위반'})
        sources=[{'source_run_id':initial,'source_case_id':i} for i in ['eval-008','eval-009']]
        release=send('POST','/releases',json={'name':'환불 수정 후보 검토 · 시나리오 데모','initial_run_id':initial,'candidate_run_id':candidate,'requirements':[REF],'reproduction_sources':sources})
        assert release['comparison']['allowed'] and release['approval_allowed']
        assert all(r['status']=='passed' for r in release['reproduction']['used_cases'])
        send('POST',f"/releases/{release['id']}/reviews",json={'reviewer':'시연 검토자','decision':'approve','reason':'동일 세트·정책에서 환불 60%→100%, 재현 2건 통과 확인. 시나리오 데모이며 독립 실모델 성능 승인을 의미하지 않음'})
        artifact=send('POST',f"/releases/{release['id']}/exports")
        exported=send('GET',artifact['json_url'])
        md=c.get(artifact['markdown_url']);md.raise_for_status()
        assert exported['candidate_run']['id']==candidate
        assert exported['candidate_run']['snapshot']['dataset_version']==dataset['version']
        assert '시나리오 데모' in md.text and initial in md.text and candidate in md.text
        (output/'release.json').write_text(json.dumps(exported,ensure_ascii=False,indent=2),encoding='utf-8')
        (output/'release.md').write_text(md.text,encoding='utf-8')
        # Revising policy/requirement creates new rows, never changes old evidence/export.
        send('POST','/policies',json={'identifier':'POL-REFUND-001','version':2,'config':{'refund_min_recall':.5,'refund_max_drop':.5}})
        if not any(r['identifier']==REF['identifier'] and r['version']==2 for r in send('GET','/requirements')):
            send('POST','/requirements',json={**{k:requirement[k] for k in ['identifier','title','owner','status','mandatory']},'verification_condition':'개정 데모: 후보 환불 재현율 50% 이상, 하락 50%p 이하','version':2,'policy_identifier':'POL-REFUND-001','policy_version':2})
        assert send('GET','/runs/'+initial)==old
        assert send('GET',artifact['json_url'])==exported
        evidence={'initial_run_id':initial,'candidate_run_id':candidate,'release_id':release['id'],'failed_release_id':failure['id'],'artifact':artifact,
                  'approval_rejected_status':blocked.status_code,'policy_revision_preserved_history':True,'url':f"http://localhost:8080/?release={release['id']}"}
        (output/'demo.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(evidence,ensure_ascii=False))

if __name__=='__main__':main()
