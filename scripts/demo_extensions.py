"""Verify saved CLI reports, immutable dataset creation, and review history via HTTP."""
import json
import time
from pathlib import Path
import httpx

def main():
    root=Path('reports')
    scenario=json.loads((root/'scenario/report.json').read_text(encoding='utf-8'))
    local=json.loads((root/'local/report.json').read_text(encoding='utf-8'))
    assert scenario['exit_code']==1 and local['exit_code']==0
    run_id=scenario['run_id'];base=scenario['snapshot']['dataset_id']
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as c:
        def send(method,path,**kwargs):
            r=c.request(method,path,**kwargs);r.raise_for_status();return r.json()
        before=send('GET','/datasets/'+base)
        before_run=send('GET','/runs/'+run_id)
        task=send('POST',f'/runs/{run_id}/analyses',json={'provider':'local'})
        for _ in range(100):
            analyses=send('GET',f'/runs/{run_id}/analyses')
            analysis=next(x for x in analyses if x['id']==task['analysis_id'])
            if analysis['status'] in ['succeeded','failed']:break
            time.sleep(.1)
        assert analysis['status']=='succeeded'
        selected=[r['case_id'] for r in scenario['result']['cases'] if r['baseline']==r['expected_label'] and r['candidate']!=r['expected_label']]
        body={'base_dataset_id':base,'case_ids':selected+selected}
        child=send('POST',f'/runs/{run_id}/dataset-versions',json=body)
        repeat=send('POST',f'/runs/{run_id}/dataset-versions',json=body)
        assert child['id']==repeat['id']
        detail=send('GET','/datasets/'+child['id'])
        assert send('GET','/datasets/'+base)==before
        assert len(detail['cases'])==len(before['cases'])==20
        assert len(detail['sources'])==2
        assert send('GET','/runs/'+run_id)==before_run
        history=send('GET',f'/runs/{run_id}/reviews')
        if not history:
            send('POST',f'/runs/{run_id}/reviews',json={'reviewer':'로컬 데모 검토자','decision':'hold','reason':'환불 재현율 40%p 하락 및 두 회귀 사례 확인'})
            history=send('GET',f'/runs/{run_id}/reviews')
        evidence={'scenario_run_id':run_id,'local_run_id':local['run_id'],'selected_case_ids':selected,'analysis':analysis,'new_dataset':detail,'old_dataset_preserved':True,'duplicate_request_reused':True,'reviews':history}
        (root/'demo-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'new_dataset_id':child['id'],'version':child['version'],'cases':len(detail['cases']),'sources':len(detail['sources']),'old_dataset_preserved':True},ensure_ascii=False))

if __name__=='__main__':main()
