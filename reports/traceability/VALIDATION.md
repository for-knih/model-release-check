# 3차 개발 검증 기록 · 요구사항 추적성 / 릴리스 검토

검증일: 2026-11-23 (Asia/Seoul). 외부 배포·원격 푸시·원격 Actions 실행 없음.

## 변경 파일

| 파일 | 변경 내용 |
|---|---|
| backend/traceability.py | 정책·요구사항 불변 버전, 근거 조회, 회귀 출처 연결, 릴리스 비교·승인 제한·증빙 스냅샷 |
| backend/db.py | PolicyVersion, RequirementVersion, RunRequirement, Release, ReleaseExport 및 Review의 release_id/evidence |
| migrations/versions/0003_traceability.py | 기존 실행·리뷰를 보존하는 증분 마이그레이션 |
| backend/main.py | 요구사항 지정, 적용 정책 정규화·스냅샷, 실행별 요구사항 연결, 확장 라우터 |
| backend/evaluation.py | 기존 compare()로 요구사항별 관측값·판정·위반 사례 저장 |
| backend/specs.py | 고정 수정 시나리오의 실제 파일 해시·설정 식별 |
| data/scenario_repaired.json | 환불 회귀 2건을 수정한 별도 고정 예측. 실제 학습 결과 아님 |
| scripts/pr_check.py | --requirement, --scenario-variant, 기존 종료 코드·보고서·멱등성 재사용 |
| scripts/demo_traceability.py | 실제 HTTP API로 실패→연결→동일 조건 수정→검토→JSON/Markdown 내보내기 |
| frontend/src/TraceWorkspace.tsx | 한국어 요구사항→실행→회귀→재검증→검토 추적표, 승인 제한·증빙 다운로드 |
| frontend/src/main.tsx, style.css | 추적 워크스페이스 통합, 기존 실행 단독 검토와 릴리스 검토 구분 |
| tests/test_traceability.py | 요구사항 보존·승인 제한·중복·비교·증빙·독립 세트 검증 |
| tests/test_migrations.py, test_platform.py | 기존 리뷰 보존 업/다운 테스트, 신규 모듈의 테스트 DB 격리 |
| README.md | 요구사항 정의/테스트 추적표, API·CLI·3분 데모·확장 ERD·검증 범위 |

## 실제 검사

- `python -m pytest tests -q -p no:cacheprovider --tb=short`: **45 passed**, 최종 10.32초. Starlette/AnyIO 및 TestClient timeout DeprecationWarning 65건. 실패 없음.
- `node node_modules/typescript/bin/tsc --noEmit`: 성공.
- `node build.mjs`: **30 modules transformed**, Vite 프로덕션 빌드 성공(최종 1.14초).
- `python -m alembic upgrade head`, `current`: 성공, **0003 (head)**.
- SQLite FK를 켠 상태에서 기존 실행·리뷰 삽입 → 0003 업그레이드 → 기존 사유와 NULL 컨텍스트 보존 → 다운그레이드 보존 확인.
- `git diff --check`: 통과(Windows 줄바꿈 변환 안내만 발생).

## 실제 HTTP 시연

요구사항 `REQ-REFUND-001 v1`, 정책 `POL-REFUND-001 v1`: 후보 환불 재현율 ≥85%, 기준 대비 하락 ≤5%p.

| 시나리오 | 기준 정확도 | 후보 정확도 | 후보 Macro F1 | 기준→후보 환불 재현율 | 요구사항 | PR CLI |
|---|---:|---:|---:|---|---|---:|
| 최초 고정 예측 | 60% | 85% | 84.66% | 100% → 60% | 실패 | 1 |
| 수정 고정 예측 | 60% | 95% | 94.95% | 100% → 100% | 통과 | 0 |

동일 테스트 세트 SHA256·동일 정책 버전에서 수정 전후 **후보 정확도 +10%p, 환불 재현율 +40%p**. 수정 시나리오는 실제 모델 개선이 아닌 **시나리오 데모**로 UI/보고서에 표시했습니다.

- 최초 실행 `a764c143-38cd-4cf0-bd2f-019d69e8e983`.
- 수정 실행 `c27645af-0337-44e8-bd8d-f61a7d24e24e`.
- 대표 회귀 `eval-008`, `eval-009`: 최초 환불→기타, 수정 후 환불 정답. 환불 실제 표본 5건.
- 기존 세트에 사례 추가 **0건**, 출처 **2건** 연결. 중복 선택에도 원본 ID·버전·원문 유지.
- 실패 실행에 일반 승인 시도: **409**, 제한 사유 반환. 보류 기록 성공.
- 수정 후보 릴리스: 시스템 통과와 별도 검토자 승인 및 사유 저장. Review evidence에 최초·수정 실행 ID와 적용 요구사항 판정 기록.
- 재현 사례 **2/2 통과**. 수정에 쓰지 않은 부분집합 **18건**, 정확도 **94.44%**, 환불 **100% / 3건**. 독립 평가 세트로 표시하지 않음.
- 별도 독립 실행 미지정: **독립 평가 미검증**. 별도 세트 검증은 자동 테스트에서 별도 실행의 모델·커밋·정책 일치와 원문 중복 거부를 확인.
- 정책 v2 개정 후에도 과거 실행 및 이미 내보낸 JSON 내용이 동일함을 실제 HTTP에서 assert.
- 내보낸 실행 ID·데이터 버전·스냅샷·지표가 저장된 평가 기록과 일치함을 assert.

스크립트 결과와 최종 릴리스·보고서 ID는 `demo.json`에 저장됩니다. `original-pr.json/md`, `repaired-pr.json/md`, `release.json/md`가 증빙입니다.

## 화면 검증

화면 버튼 1→2→3→4→검토 결정→6을 실제 클릭했습니다. 요구사항 실패 원문, 출처 추가 2/데이터 추가 0, 동일 조건 개선, 재현 사례와 나머지 18건 구분, 검토자 승인 이력과 JSON/Markdown 링크를 확인했습니다.

- 화면 최초 실행 `9877041d-58ac-4f04-8cdf-3abc4f4113cd`.
- 화면 수정 실행 `2dcd94db-222a-4adb-ac12-c5f584887c6e`.
- 화면 릴리스 `6bdbf0a4-2246-49a8-ad4d-e3845cd0fc5d`.
- 화면 보고서 `b19ea91f-0070-443e-b937-66021b129676`.
- `ui-release.json/md`를 다운로드 API로 저장하고 두 원본 실행의 스냅샷과 일치함을 확인했습니다.
- `ui-review.jpg`: 저장된 결정·근거 실행·두 보고서 링크 스크린샷. 전체 페이지 캡처는 브라우저에서 실패해 전체 캡처 파일은 제공하지 않습니다.

## 재현 명령

```bash
alembic upgrade head
QUEUE_MODE=thread uvicorn backend.main:app --host 127.0.0.1 --port 8000
# 다른 터미널
python -m scripts.demo_traceability
pytest tests -q
cd frontend
npm ci
npm run build
cd ..
python -m http.server 8080 --bind 127.0.0.1 --directory frontend/dist
```

PowerShell에서는 `$env:QUEUE_MODE='thread'`를 사용합니다. PostgreSQL/RQ 경로는 `docker compose up --build -d`입니다.

## 확인하지 못한 항목

- Docker 실행 파일이 없어 Compose 및 실제 PostgreSQL·Redis/RQ 통합을 실행하지 못했습니다. SQLite + thread 실제 HTTP, 워커 함수, 마이그레이션을 검증했습니다.
- GitHub Actions와 HF 외부 호출은 실행하지 않았습니다. 기존 분석 테스트는 가짜 공급자를 유지합니다.
- 고정 예측 수정이 실제 학습·일반화 성능 개선을 뜻하지 않습니다. 이번 시나리오에는 별도 독립 평가 세트가 없습니다.
- 불변성·승인 제한은 공개 API와 저장된 스냅샷 범위이며 DB 관리자에 의한 직접 수정까지 막는 트리거는 구현하지 않았습니다.
- 원격 푸시와 외부 배포를 수행하지 않았습니다.
