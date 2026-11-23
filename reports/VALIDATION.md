# 로컬 구현·검증 기록

검증일: 2026-11-23 (Asia/Seoul)

## 변경 파일

- `backend/specs.py`: 유효 설정 정규화, 구현·데이터 해시, 커밋 SHA와 표시용 버전 이름 분리.
- `backend/main.py`: 설정 조회, 모델 설정 요청 확장, 별도 분석 요청/상태, 세트 목록/상세, 새 버전 생성.
- `backend/models.py`, `evaluation.py`: 실제 후보 하이퍼파라미터 적용, 스냅샷 일치 검증, 기존 지표·환불 정책·예측 재사용.
- `backend/analysis.py`: 로컬 라벨 전이 집계, 선택 HF 분석, 엄격 응답·근거 ID 검증. 품질/검토 테이블 미수정.
- `backend/db.py`, `migrations/versions/0002_analysis_sources.py`: 분석 작업, 부모 버전, 사례 출처 제약·관계. `0001` 기존 구조 보존.
- `scripts/pr_check.py`, `demo_extensions.py`: CLI 종료 코드·보고서·멱등성, HTTP 전체 흐름 검증.
- `frontend/src/AnalysisPanel.tsx`, `main.tsx`, `style.css`: 분석 상태·근거 원문·실패 사례 선택·새 버전·재평가 준비.
- `frontend/build.mjs`, `vite.config.ts`, package/lock: 타입 검사와 Vite 프로덕션 빌드.
- `.github/workflows/pr-quality.yml`: PR head 검증, Summary/Artifact, 완료 DB 캐시.
- `tests/test_extensions.py`, `test_migrations.py`, `test_platform.py`: 추가 테스트 및 메모리 SQLite 격리.
- `README.md`, `.env.example`, `compose.yaml`, Docker 구성: 실행/데모/API/ERD/검증 한계 문서화.

## 실제 실행 결과

`pytest tests -q -p no:cacheprovider --tb=short`: 최종 **31 passed**, 18.92초. Starlette/AnyIO 및 TestClient timeout 관련 DeprecationWarning 49건. 테스트 실패 없음. SQLite FK가 활성화된 기존 사례 데이터의 마이그레이션 보존까지 확인했습니다.

`node node_modules/typescript/bin/tsc --noEmit`: 성공.

`node build.mjs`: Vite 6.4.1 **29 modules transformed**, 프로덕션 빌드 성공(최종 1.61초). 표준 환경에서는 `npm run build`가 두 명령을 수행합니다.

Alembic `upgrade head`: SQLite DB에 성공. 별도 테스트로 `0001` 데이터 삽입 → `0002` 업그레이드 → 다운그레이드 → 재업그레이드 시 기존 데이터 보존 확인.

| 모드 | 기준 정확도 | 후보 정확도 | 기준 Macro F1 | 후보 Macro F1 | 환불 재현율 기준→후보 | CLI |
|---|---:|---:|---:|---:|---|---:|
| 고정 예측 시나리오 | 60% | 85% | 61.11% | 84.66% | 100% → 60% | 1 |
| 실제 로컬 모델 | 70% | 75% | 69.20% | 74.85% | 100% → 100% | 0 |

환불 최소 80%, 허용 하락 10%p. 시나리오에서 최소값 위반 및 40%p 하락 두 사유로 보류. 환불 실제 표본 5건이며 기준만 정답인 회귀 사례는 `eval-008`, `eval-009` 두 건.

- 시나리오 실행: `188c178d-75e0-44af-84ad-e1cc2b4006b7`
- 실제 로컬 실행: `c9000e4d-e7ee-4558-af42-c901fa01e1bd`
- `--candidate-version renamed-only`로 시나리오 CLI 재실행: **같은 실행 ID**, 종료 코드 1.
- `--timeout 0`: **종료 코드 2**, JSON·Markdown 오류 보고서 생성.
- 로컬 별도 분석: succeeded, `환불 → 기타 2건`, AI 추론 아님.
- 브라우저에서 분석 근거 ID 클릭 → 원문/기대/기준/후보 표시, 보류 사유 저장 후 이력 표시 확인.
- 새 데이터셋: `3449b205-0ad9-4a69-bcba-f9af421b2857`, 버전 `b84322f37aa0b7b565f06277ee44da86537881ea17d1480fae42bd6306d546fd`.
- 원본 20건 보존, 새 버전 20건·출처 2건, 같은 요청의 자식 ID 재사용 확인.
- `python -m scripts.demo_extensions`: HTTP 검증 성공, `demo-evidence.json` 저장.
- 생성한 자식 버전으로 실제 로컬 재평가: `231577cc-74eb-4a34-a281-0fcfb3172a55`, 정확도 70% → 75%, 환불 재현율 100% 유지, 종료 코드 0 (`revalidation/report.json`).
- Compose 및 GitHub Actions YAML 파싱 검사 성공. 실제 서비스 기동/원격 실행을 대체하는 검증은 아님.

원본 보고서: `scenario/report.json`, `local/report.json`, `scenario-retry/report.json`, `error/report.json`, `demo-evidence.json`. 화면 증거: `demo-ui.jpg`.

## 재현 명령

```bash
alembic upgrade head
QUEUE_MODE=thread uvicorn backend.main:app --host 127.0.0.1 --port 8000
# 다른 터미널
python -m scripts.pr_check --dataset-version sample --commit-sha local-demo-pr-001 --mode scenario --output-dir reports/scenario
# 예상 exit 1
python -m scripts.pr_check --dataset-version sample --commit-sha local-demo-pr-001 --mode local --output-dir reports/local
# 예상 exit 0
python -m scripts.demo_extensions
pytest tests -q
cd frontend
npm ci
npm run build
```

## 환경 제한과 미검증

- Docker 실행 파일과 로컬 PostgreSQL/Redis 서버가 없어 Compose 실제 기동과 PostgreSQL/RQ 통합 실행은 수행하지 못함. Compose/워크플로 YAML은 파싱 검사, 큐 실패·재시도·중복은 주입 테스트, 워커 함수는 실제 실행함.
- 로컬 실제 HTTP는 SQLite + 명시적 thread 개발 모드. RQ 내구성을 이 결과로 주장하지 않음.
- HF 분류/생성은 실제 외부 호출하지 않음. AI 테스트는 가짜 공급자로 실행함.
- GitHub Actions, DB 캐시 복원, Job Summary의 GitHub 화면 표시는 원격 실행하지 않음.
- Windows 샌드박스에서 pip 임시 폴더와 npm/esbuild 자식 프로세스에 접근 거부가 발생함. 작업 폴더에 PyPI 휠을 추출해 의존성을 준비하고 TypeScript 인프로세스 변환으로 빌드함. pytest는 메모리 SQLite를 사용함.
- 외부 배포·원격 푸시·저장소 공개를 수행하지 않음.
