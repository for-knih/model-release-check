"""API client for PR quality gates. python -m scripts.pr_check --help"""
import argparse
import html
import json
import os
from pathlib import Path
import time
import httpx

def cell(value):
    return html.escape(str(value)).replace('|','&#124;').replace('\n',' ')

def markdown(report):
    lines=['# AI 모델 변경 검증', '', f"- 결과: **{ {0:'통과',1:'품질 기준 미달 / 평가 불가',2:'실행 오류'}[report['exit_code']] }**",
           f"- 실행 ID: {cell(report.get('run_id','없음'))}", f"- 평가 방식: {cell(report.get('mode','알 수 없음'))}"]
    if report.get('error'):
        lines.extend(['',cell(report['error'])])
    if report.get('result'):
        r=report['result']
        lines.extend(['', '| 지표 | 기준 | 후보 |', '|---|---:|---:|'])
        for key,title in [('accuracy','전체 정확도'),('macro_f1','Macro F1')]:
            lines.append(f"| {title} | {r['baseline'][key]:.1%} | {r['candidate'][key]:.1%} |")
        for label,v in r['baseline']['classes'].items():
            b,c=v['recall'],r['candidate']['classes'][label]['recall']
            fmt=lambda x:'평가 불가' if x is None else f'{x:.1%}'
            lines.append(f"| {cell(label)} 재현율 (실제 {v['support']}건) | {fmt(b)} | {fmt(c)} |")
        lines.extend(['','## 보류 사유',*['- '+cell(x) for x in r['reasons']]])
        if not r['reasons']:lines.append('- 설정된 환불 기준 충족')
        lines.extend(['','## 대표 실패 사례','| 사례 ID | 문의 | 기대 | 기준 | 후보 |','|---|---|---|---|---|'])
        for row in report['representative_failures']:
            lines.append('| '+' | '.join(cell(row[k]) for k in ['case_id','text','expected_label','baseline','candidate'])+' |')
        spec=report.get('snapshot',{})
        lines.extend(['',f"- 커밋 SHA: {cell(spec.get('commit_sha',''))}", f"- 설정 지문: {cell(spec.get('configuration_fingerprint',''))}",
                      f"- 기준 버전: {cell(spec.get('baseline_version',''))}",f"- 후보 버전: {cell(spec.get('candidate_version',''))}",
                      f"- 버전 이름(표시용): {cell(spec.get('candidate_version_label',''))}"])
        for requirement in r.get('requirements',[]):
            req=requirement['requirement'];p=req['policy']
            lines.append(f"- 요구사항: {cell(req['identifier'])} v{req['version']} / 정책 {cell(p['identifier'])} v{p['version']} / {cell(requirement['verdict']['status_label'])}")
    return '\n'.join(lines)+'\n'

def run_check(client, body, timeout=120, poll_interval=.5):
    report={'exit_code':2,'mode':'시나리오 데모 (고정 예측)' if body['mode']=='scenario' else '실제 로컬 모델 평가'}
    started=time.monotonic()
    def send(method,path,**kwargs):
        remaining=timeout-(time.monotonic()-started)
        if remaining<=0:raise TimeoutError('평가 대기 시간 초과')
        response=client.request(method,path,timeout=min(remaining,30),**kwargs)
        response.raise_for_status()
        return response.json()
    try:
        resolved=send('POST','/run-specs',json=body)
        key='pr-'+resolved['fingerprint']
        execution=send('POST','/runs',json=body,headers={'Idempotency-Key':key})
        report['run_id']=execution['run_id']
        while True:
            run=send('GET','/runs/'+report['run_id'])
            if run['status']=='failed':raise RuntimeError('평가 작업 실패: '+str(run.get('error')))
            if run['status']=='succeeded':break
            if run['status'] not in ['queued','running']:raise RuntimeError('알 수 없는 평가 상태')
            remaining=timeout-(time.monotonic()-started)
            if remaining<=0:raise TimeoutError('평가 대기 시간 초과')
            time.sleep(min(poll_interval,remaining))
        result=run['result']
        if result['recommendation'] not in ['approve','hold']:
            raise ValueError('잘못된 품질 판정 응답')
        failures=[r for r in result['cases'] if r['candidate']!=r['expected_label']]
        failures.sort(key=lambda r:r['baseline']!=r['expected_label'])
        report.update(exit_code=0 if result['recommendation']=='approve' and result['refund_evaluable'] else 1,
                      snapshot=run['snapshot'],result=result,representative_failures=failures[:5])
    except (httpx.HTTPError,TimeoutError,RuntimeError,ValueError,KeyError,TypeError) as exc:
        report['error']=str(exc)
        if isinstance(exc,httpx.HTTPStatusError):
            try:
                report['run_id']=exc.response.json()['detail']['run_id']
            except (ValueError,KeyError,TypeError):pass
    return report

def json_arg(value):
    try:
        parsed=json.loads(Path(value[1:]).read_text(encoding='utf-8') if value.startswith('@') else value)
        if not isinstance(parsed,dict):raise ValueError('JSON 객체가 필요합니다')
        return parsed
    except (OSError,ValueError) as exc:raise argparse.ArgumentTypeError(str(exc)) from exc

def parser():
    p=argparse.ArgumentParser(description='AI 모델 PR 자동 검증 · 종료 코드 0/1/2')
    p.add_argument('--api-url',default='http://127.0.0.1:8000')
    p.add_argument('--dataset-version',required=True,help='SHA256 버전 또는 sample')
    p.add_argument('--commit-sha',default=os.getenv('GITHUB_SHA'),required=not bool(os.getenv('GITHUB_SHA')))
    p.add_argument('--mode',choices=['local','scenario'],default='local')
    p.add_argument('--scenario-variant',choices=['original','repaired'],default='original')
    p.add_argument('--requirement',action='append',default=[],help='ID@버전 (예: REQ-REFUND-001@1), 반복 가능')
    p.add_argument('--baseline-config',type=json_arg,default={'adapter':'keyword','rules_version':'v1'})
    p.add_argument('--candidate-config',type=json_arg,default={'adapter':'local','C':4,'ngram_min':2,'ngram_max':4})
    p.add_argument('--baseline-version',default='keyword-v1',help='표시용 이름; 설정 변경으로 취급하지 않음')
    p.add_argument('--candidate-version',default='candidate-v1',help='표시용 이름; 설정 변경으로 취급하지 않음')
    p.add_argument('--prompt-version',default='none',help='표시용; 분류 어댑터는 프롬프트를 사용하지 않음')
    p.add_argument('--refund-min-recall',type=float,default=.8)
    p.add_argument('--refund-max-drop',type=float,default=.1)
    p.add_argument('--timeout',type=float,default=120)
    p.add_argument('--output-dir',type=Path,default=Path('reports/pr'))
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    report={'exit_code':2,'error':'초기화 오류'}
    try:
        with httpx.Client(base_url=args.api_url,timeout=30) as client:
            if args.dataset_version=='sample':
                response=client.post('/datasets/sample');response.raise_for_status();dataset=response.json()
            else:
                response=client.get('/datasets',params={'version':args.dataset_version});response.raise_for_status()
                datasets=response.json()
                if len(datasets)!=1:raise ValueError('데이터셋 버전이 없거나 여러 이름에 존재합니다')
                dataset=datasets[0]
            body={'dataset_id':dataset['id'],'mode':args.mode,'commit_sha':args.commit_sha,
                  'baseline_config':args.baseline_config,'candidate_config':args.candidate_config,
                  'baseline_version_label':args.baseline_version,'candidate_version_label':args.candidate_version,
                  'prompt_version':args.prompt_version,'policy':{'refund_min_recall':args.refund_min_recall,'refund_max_drop':args.refund_max_drop}}
            body['scenario_variant']=args.scenario_variant
            body['requirements']=[{'identifier':value.rsplit('@',1)[0],'version':int(value.rsplit('@',1)[1])} for value in args.requirement]
            report=run_check(client,body,args.timeout)
    except (httpx.HTTPError,ValueError,KeyError,IndexError) as exc:
        report={'exit_code':2,'error':str(exc)}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=markdown(report)
    (args.output_dir/'report.md').write_text(summary,encoding='utf-8')
    print(summary)
    return report['exit_code']

if __name__=='__main__':raise SystemExit(main())
