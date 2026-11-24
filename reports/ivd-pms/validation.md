# IVD 변경 영향평가·불만·CAPA 구현 검증 기록

확인일: 2026-11-24 (Asia/Seoul). **가상 제품 · 검토용 예시**.

## 변경 파일

- 서버: `backend/ivd.py`, `backend/ivd_models.py`, `backend/ivd_changes.py`, `backend/ivd_pms.py`, `backend/ivd_pms_models.py`, `backend/main.py`
- 마이그레이션: `migrations/env.py`, `migrations/versions/0005_ivd_changes.py`, `migrations/versions/0006_ivd_pms.py`
- 화면: `frontend/src/IVDWorkspace.tsx`, `IVDChangesWorkspace.tsx`, `PMSWorkspace.tsx`, `main.tsx`, `style.css`
- 테스트: `tests/test_platform.py`, `tests/test_migrations.py`, `tests/test_ivd_changes.py`, `tests/test_ivd_pms.py`
- 시연·증빙 검증: `scripts/demo_ivd_changes.py`, `scripts/demo_ivd_pms.py`, `scripts/verify_ivd_artifacts.py`
- 문서·의존성: `README.md`, `docs/ivd-change-pms.md`, `requirements.txt` (Windows Asia/Seoul 시간대 데이터)
- 생성 결과: `reports/ivd-changes/`, `reports/ivd-pms/`

## 실행한 검증

```bash
python -m alembic upgrade head
python -m alembic current
python -m pytest tests -q -p no:cacheprovider --tb=short
cd frontend
node node_modules/typescript/bin/tsc --noEmit
node build.mjs
cd ..
python scripts/demo_ivd_changes.py
python scripts/demo_ivd_pms.py
python scripts/verify_ivd_artifacts.py
```

실제 환경에서는 번들 Python과 로컬 설치 의존성(`work/packages`)을 사용했습니다. API는 `QUEUE_MODE=thread`, SQLite `local.db`, loopback 8000, 정적 UI는 loopback 8080입니다. 표준 설치·실행 명령은 README에 있습니다.

- 최종 pytest: **75 passed, 64 warnings in 23.95s**. 경고는 Starlette/AnyIO TestClient의 deprecated alias/timeout 사용입니다. 로그: [test-results.txt](test-results.txt).
- Alembic: **0006 (head)**. 업/다운그레이드와 기존 IVD 데이터 보존 테스트 포함.
- TypeScript: 종료 코드 0. Vite: **33 modules**, 1.10초, 빌드 성공.
- 실제 동시 제품 변경 확정: SQLite의 별도 연결 두 요청에서 한 요청 성공·한 요청 충돌, 결과 중복 없음.
- HTTP 데모: 테스트 클라이언트가 아닌 실행 중인 FastAPI에 요청. JSON/Markdown 내려받기 성공.
- 저장된 기록과 내보내기 대조: [artifact-checks.json](artifact-checks.json)의 모든 확인 값 true.
- 브라우저: 제품 필터, 실제 로트 번호, 조사 원인·근거, 당시 문서, 계획 v1/v2, 평가 실패/통과, 최종 변경 문서 연결 표시 확인. 변경 화면 콘솔 오류 없음. [covid-effectiveness.jpg](covid-effectiveness.jpg).

## 시연 확인 값

| 흐름 | 실제 확인 |
|---|---|
| HIV EU 증빙 변경 | 정확한 성능 증빙 참조 섹션 1개만 영향 후보; 미완료 승인 409; 이전 패키지 보존; 승인 재전송 같은 결과 |
| COVID 제품명 변경 | KR/EU 개요·표시사항 총 4개 후보; 시장 판단 독립 저장; 후속 2개 패키지 |
| HIV 불만·CAPA | 미확인 로트 사후 연결, 당시 설명서 보존, 즉시·시정 조치, 실행 증빙과 별도 효과성 증빙 |
| HIV 평가 | 수량·관찰·진행 변경으로 평가 대기 → 설명서 새 버전 확정 → 전 1/1,000, 후 0/1,000; 기준 0.5 이하로 통과·종결 |
| COVID 불만 | 동일 사건의 원본 접수 2건 / 사건 1건; 후속 기간의 독립 사건은 별도 1건 |
| COVID 평가 | 계획 v1 조치 후 1/1,000 > 0.5로 기준 미달 → 재조치 → 계획 v2 조치 후 0/1,000 통과·종결; 같은 재평가 요청의 ID 재사용 |

최신 PMS 예시:

- HIV 불만 `4955534e-1304-4cb3-a86a-9eaacc50122e`
- COVID 불만 `2b3baaf1-0fb3-45fb-b770-df5f50bed604`
- [HIV JSON](hiv-outdated-ifu.json), [HIV Markdown](hiv-outdated-ifu.md)
- [COVID JSON](covid-missing-label.json), [COVID Markdown](covid-missing-label.md)
- 요청/결과 ID·계획·기간·원본/사건·분모·발생률: [demo.json](demo.json)
- 변경 검토 보고서: [HIV](../ivd-changes/hiv-eu-change.md), [COVID](../ivd-changes/covid-name-change.md)

미래 접수/관찰을 합성 모드로 시연했습니다. 실제 관찰 기간이 경과하거나 실제 제품의 효과성을 입증한 결과가 아닙니다. 기존 시연을 재실행하며 쌓인 다른 로트의 기록은 삭제하지 않았습니다. 목록 전체 건수와 해당 평가 기간·로트 코호트 집계는 범위가 다릅니다.

## 미검증·제한

- Docker 실행 환경이 없어 Compose/PostgreSQL/Redis/RQ의 실제 통합과 PostgreSQL 행 잠금 동작은 미검증. SQLite API·마이그레이션·동시 CAS는 검증했습니다.
- 실제 Hugging Face 호출은 하지 않았습니다. 가짜 공급자로 문장 스키마·연결 근거 ID 검증 및 오류 시 상태 불변을 테스트했습니다.
- 실제 임상 성능·유통 자료·법정 보고 여부/기한은 검증하지 않았습니다. 공식 출처 레지스트리를 재사용하고 담당자의 근거·조항·적용일·사유 기록 기능만 제공합니다. 보고 기본 상태는 검토 필요, 기한 미확정입니다.
- 외부 배포, 원격 푸시, 기관 전송은 하지 않았습니다.
