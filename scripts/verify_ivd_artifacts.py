"""Read-only verification of HTTP demo exports against persisted records."""
import json
from pathlib import Path
import httpx

def main():
    out=Path('reports/ivd-pms');demo=json.loads((out/'demo.json').read_text(encoding='utf-8'))
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as c:
        def get(path):
            r=c.get(path);r.raise_for_status();return r.json()
        for key,name in [('hiv','hiv-outdated-ifu'),('covid','covid-missing-label')]:
            d=demo[key];saved=json.loads((out/(name+'.json')).read_text(encoding='utf-8'))
            assert get(d['export']['json_url'])==saved
            live=get('/ivd/complaints/'+d['complaint_id'])
            assert saved['id']==live['id'] and saved['lot']==live['lot']
            assert saved['capas'][0]['status']=='closed'
            assert saved['capas'][0]['evaluations']==live['capas'][0]['evaluations']
            assert saved['reporting_review']['deadline_status']=='미확정'
        hiv=get('/ivd/complaints/'+demo['hiv']['complaint_id']);covid=get('/ivd/complaints/'+demo['covid']['complaint_id'])
        assert next(m for m in hiv['lot']['snapshot']['mappings'] if m['section']=='labeling')['document']['id']==demo['hiv']['old_document_id']
        assert demo['hiv']['old_document_id']!=demo['hiv']['final_document_id']
        result=hiv['capas'][0]['evaluations'][-1]
        execution_ids={id for a in hiv['capas'][0]['actions'] for id in a['execution']['evidence_ids']}
        assert not execution_ids.intersection(result['snapshot']['result_evidence_ids'])
        assert [r['status'] for r in covid['capas'][0]['evaluations']]==['failed','passed']
        first=covid['capas'][0]['evaluations'][0]['snapshot']['cohorts']['before']
        assert (first['raw_receipts'],first['incidents'],first['quantity'])==(2,1,1000)
        changes=json.loads(Path('reports/ivd-changes/demo.json').read_text(encoding='utf-8'))
        for name,id in [('hiv-eu-change',changes['hiv_change_id']),('covid-name-change',changes['covid_change_id'])]:
            report=json.loads(Path(f'reports/ivd-changes/{name}.json').read_text(encoding='utf-8'))
            live=get('/ivd/changes/'+id)
            assert report['id']==live['id'] and report['result']==live['result']
        checks={'frozen_exports_match_database':True,'old_lot_document_preserved':True,'execution_and_effectiveness_evidence_separate':True,'duplicate_receipts_vs_incidents':[2,1],'covid_failed_then_passed':True,'change_report_ids_and_results_match_database':True}
        (out/'artifact-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
