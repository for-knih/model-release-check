"""Run against a real listening API; preserve metrics and reviewer history."""
import json
import time
import uuid
import httpx

def main():
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as c:
        dataset=c.post('/datasets/sample');dataset.raise_for_status()
        reports={}
        for mode in ['scenario','local']:
            response=c.post('/runs',headers={'Idempotency-Key':str(uuid.uuid4())},json={'dataset_id':dataset.json()['id'],'mode':mode})
            response.raise_for_status();run_id=response.json()['run_id']
            for _ in range(120):
                response=c.get('/runs/'+run_id);response.raise_for_status();run=response.json()
                if run['status'] in ['succeeded','failed']:break
                time.sleep(.25)
            assert run['status']=='succeeded',run
            review=c.post(f'/runs/{run_id}/reviews',json={'reviewer':'데모 검토자','decision':'hold','reason':'환불 사례 원문 및 재현율을 확인했습니다. 추가 검증 후 재검토합니다.'})
            review.raise_for_status()
            history=c.get(f'/runs/{run_id}/reviews');history.raise_for_status()
            reports[mode]={'run':run,'reviews':history.json()}
        print(json.dumps(reports,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
