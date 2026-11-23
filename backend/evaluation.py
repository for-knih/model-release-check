from datetime import datetime, timezone
from sqlalchemy import select, func
from sklearn.metrics import accuracy_score, f1_score, recall_score
from .db import Session, Run, Case, Prediction
from .models import LABELS, KeywordAdapter, LocalAdapter, HuggingFaceAdapter
from .specs import file_hash
from .models import DATA
from pathlib import Path

def metrics(expected, predicted):
    recall = recall_score(expected, predicted, labels=LABELS, average=None, zero_division=0)
    return {'accuracy': accuracy_score(expected, predicted), 'macro_f1': f1_score(expected, predicted, labels=LABELS, average='macro', zero_division=0),
            'classes': {label: {'recall': float(recall[i]) if label in expected else None, 'support': expected.count(label)} for i, label in enumerate(LABELS)}}

def compare(rows, policy):
    expected = [r['expected_label'] for r in rows]
    baseline = metrics(expected, [r['baseline'] for r in rows])
    candidate = metrics(expected, [r['candidate'] for r in rows])
    b, c = baseline['classes']['환불']['recall'], candidate['classes']['환불']['recall']
    reasons = []
    if c is None:
        reasons.append('환불 사례 0건: 환불 기준 평가 불가')
    else:
        if c < policy['refund_min_recall']:
            reasons.append(f"환불 재현율 {c:.1%} < 최소 {policy['refund_min_recall']:.1%}")
        if b - c > policy['refund_max_drop'] + 1e-12:
            reasons.append(f"환불 재현율 하락 {b-c:.1%}p > 허용 {policy['refund_max_drop']:.1%}p")
    return {'baseline': baseline, 'candidate': candidate, 'recommendation': 'hold' if reasons else 'approve', 'reasons': reasons, 'refund_evaluable': c is not None}

def evaluate(run_id):
    with Session() as s:
        run = s.get(Run, run_id, with_for_update=True)
        if run.status == 'succeeded':
            return
        run.status, run.error = 'running', None
        s.commit()
    try:
        with Session() as s:
            run = s.get(Run, run_id)
            cases = s.scalars(select(Case).where(Case.dataset_id == run.dataset_id).order_by(Case.id)).all()
            mode = run.snapshot['mode']
            spec = run.snapshot.get('effective_spec', {})
            if spec.get('evaluation_implementation') and spec['evaluation_implementation'] != file_hash(Path(__file__)):
                raise ValueError('평가 구현이 스냅샷과 다릅니다')
            if mode == 'local' and spec.get('model_implementation') != file_hash(Path(__file__).with_name('models.py')):
                raise ValueError('모델 구현이 스냅샷과 다릅니다')
            baseline = KeywordAdapter()
            config = spec.get('candidate_config')
            candidate = (HuggingFaceAdapter(run.snapshot['candidate_version']) if run.snapshot['candidate_adapter'] == 'huggingface' else LocalAdapter(config)) if mode == 'local' else None
            if candidate and candidate.version != run.snapshot['candidate_version']:
                raise ValueError('모델 버전이 실행 스냅샷과 다릅니다')
            for case in cases:
                for role in ['baseline', 'candidate']:
                    existing = s.scalar(select(Prediction).where(Prediction.run_id == run_id, Prediction.case_id == case.id, Prediction.model_role == role))
                    if existing:
                        continue
                    if mode == 'scenario':
                        label = run.snapshot['scenario_predictions'][case.case_id][role]
                    else:
                        label = (baseline if role == 'baseline' else candidate).predict(case.text)
                    # Serialize writers on the run row, then recheck after lock acquisition.
                    s.get(Run, run_id, with_for_update=True, populate_existing=True)
                    exists = s.scalar(select(Prediction.id).where(Prediction.run_id == run_id, Prediction.case_id == case.id, Prediction.model_role == role))
                    if exists is None:
                        s.add(Prediction(run_id=run_id, case_id=case.id, model_role=role, label=label))
                    s.commit()
            predictions = s.scalars(select(Prediction).where(Prediction.run_id == run_id)).all()
            if len(predictions) != len(cases) * 2:
                raise ValueError('일부 사례 누락: 완료 불가')
            lookup = {(p.case_id, p.model_role): p.label for p in predictions}
            rows = [dict(case_id=c.case_id, text=c.text, expected_label=c.expected_label, baseline=lookup[c.id, 'baseline'], candidate=lookup[c.id, 'candidate']) for c in cases]
            run.result = {**compare(rows, run.snapshot['policy']), 'cases': rows, 'completed_at': datetime.now(timezone.utc).isoformat()}
            run.status = 'succeeded'
            s.commit()
    except Exception as exc:
        with Session() as s:
            run = s.get(Run, run_id)
            if run.status != 'succeeded':
                run.status, run.error = 'failed', str(exc)
                s.commit()
        raise
