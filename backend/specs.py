"""Effective model settings are identity; human version labels are annotations."""
import hashlib
import json
import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .models import DATA

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class BaselineConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    adapter: Literal['keyword'] = 'keyword'
    rules_version: Literal['v1'] = 'v1'

class CandidateConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    adapter: Literal['local', 'huggingface'] = 'local'
    C: float = Field(default=4, gt=0, le=100)
    ngram_min: int = Field(default=2, ge=1, le=5)
    ngram_max: int = Field(default=4, ge=1, le=6)
    model_id: str | None = None
    @model_validator(mode='after')
    def valid(self):
        if self.ngram_min > self.ngram_max:
            raise ValueError('ngram_min은 ngram_max 이하여야 합니다')
        if self.adapter == 'local' and self.model_id:
            raise ValueError('local 어댑터에는 model_id를 지정하지 않습니다')
        return self

def effective_spec(body, dataset):
    candidate = body.candidate_config or CandidateConfig(adapter=body.candidate_adapter)
    settings = candidate.model_dump()
    if candidate.adapter == 'huggingface':
        settings = {'adapter':'huggingface', 'model_id': candidate.model_id or os.getenv('HF_MODEL_ID')}
    common = {'dataset_id': dataset.id, 'dataset_version': dataset.version, 'mode': body.mode,
              'commit_sha': body.commit_sha, 'policy': body.policy.model_dump(),
              'evaluation_implementation': file_hash(Path(__file__).with_name('evaluation.py'))}
    if body.mode == 'scenario':
        common.update(baseline_config={'adapter':'fixed-scenario'}, candidate_config={'adapter':'fixed-scenario'}, scenario_hash=file_hash(DATA/'scenario.json'))
    else:
        common.update(baseline_config=body.baseline_config.model_dump(), candidate_config=settings,
                      model_implementation=file_hash(Path(__file__).with_name('models.py')))
        if candidate.adapter == 'local':
            common['training_sha256'] = file_hash(DATA/'train.csv')
    return common
