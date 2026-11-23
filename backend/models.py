import csv
import hashlib
import os
from pathlib import Path
from typing import Protocol
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

DATA = Path(__file__).resolve().parents[1] / 'data'
LABELS = ['배송', '환불', '결제', '기타']

class Adapter(Protocol):
    version: str
    def predict(self, text: str) -> str: ...

class KeywordAdapter:
    version = 'keyword-v1'
    def predict(self, text):
        for label, words in [('환불', ['환불', '반품']), ('배송', ['배송', '택배']), ('결제', ['결제', '카드'])]:
            if any(w in text for w in words):
                return label
        return '기타'

class LocalAdapter:
    def __init__(self, config=None):
        config = config or {'C':4, 'ngram_min':2, 'ngram_max':4}
        content = (DATA / 'train.csv').read_bytes()
        self.version = 'char-tfidf-logreg-v1-' + hashlib.sha256(content).hexdigest()
        with (DATA / 'train.csv').open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        self.pipeline = make_pipeline(TfidfVectorizer(analyzer='char', ngram_range=(config['ngram_min'], config['ngram_max'])), LogisticRegression(C=config['C'], random_state=42, max_iter=1000))
        self.pipeline.fit([r['text'] for r in rows], [r['expected_label'] for r in rows])
    def predict(self, text):
        return str(self.pipeline.predict([text])[0])

class HuggingFaceAdapter:
    def __init__(self, model_id=None):
        from huggingface_hub import InferenceClient
        self.version = model_id or os.environ['HF_MODEL_ID']
        self.client = InferenceClient(model=self.version, token=os.environ['HF_TOKEN'], timeout=30)
    def predict(self, text):
        result = self.client.zero_shot_classification(text, candidate_labels=LABELS)
        label = result.labels[0]
        if label not in LABELS:
            raise ValueError('허용되지 않은 모델 응답')
        return label
