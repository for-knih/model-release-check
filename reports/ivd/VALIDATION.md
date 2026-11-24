# IVD 시장별 문서 패키지 · 로컬 검증 기록

확인일: 2026-11-24 / Asia/Seoul. 구현·시연은 로컬에서만 수행했으며 원격 푸시·외부 배포 없음.

## 기존 코드 확인과 구현 범위

지정 저장소 model-release-check에는 평가 API·워커·PR CLI·릴리스 추적 모듈이 있었으나 IVD 제품·문서 모델과 HIV/COVID 가상 데이터는 없었습니다. 사용자에게 경로를 확인했고 같은 저장소를 지정받았습니다. 따라서 기존 FastAPI·SQLAlchemy Base/Session·Alembic·React와 JSON/Markdown 구조를 활용하면서 필요한 IVD 도메인 모델과 최소 가상 메타데이터를 추가했습니다. 기존 가상 제품 데이터를 재사용한 것으로 표시하지 않습니다.

제품은 `IVD-HIV-DEMO`, `IVD-COVID-DEMO`입니다. 등록 내용은 가상 문서 메타데이터와 누락 상태뿐이며 실제 성능값·검체 조건·시험 결과·규제 등급을 생성하지 않았습니다.

## 변경 파일

| 파일 | 내용 |
|---|---|
| backend/ivd_models.py | 제품, 문서/증빙 개정본, 시장별 패키지, 요구사항 매핑·증빙 연결, 보완, 검토 이벤트, 내보내기 스냅샷 |
| backend/ivd.py | 제품·시장 서버 검증, 미확인 근거 확정 방지, 개정/비교, 보완 상태 전이, 완료 제한, 선택 AI 문장별 ID 검증 |
| backend/main.py | /ivd 라우터 연결. 기존 평가 기능 보존 |
| data/ivd_sources.json | 공식 출처 번호·제목·URL·버전·확인일·확인 범위와 미확인 목록, 별도 가상 기준 |
| migrations/versions/0004_ivd.py, migrations/env.py | 기존 평가/리뷰를 변경하지 않는 독립 IVD 9개 테이블, 메타데이터 등록 |
| frontend/src/IVDWorkspace.tsx, main.tsx | ?ivd=1 화면, 제품·시장 선택, 매핑/리뷰·증빙·보완·새 버전·내보내기 |
| scripts/demo_ivd.py | HIV EU 전체 보완 흐름 및 HIV/COVID 국내 패키지 격리 실제 HTTP 시연 |
| tests/test_ivd.py, test_migrations.py, test_platform.py | IVD 기능·편집 AI 인용 재검증·0004 업/다운·테스트 세션 격리 |
| README.md | 요구사항 정의표, 출처/한계, API, 실행·데모, ERD 갱신 |

## 실제 검사

- `python -m pytest tests -q -p no:cacheprovider --tb=short`: **55 passed**, 14.50초. Starlette/AnyIO 및 TestClient timeout 관련 DeprecationWarning 58건, 실패 없음.
- `node node_modules/typescript/bin/tsc --noEmit`: 성공.
- `node build.mjs`: Vite **31 modules transformed**, 프로덕션 빌드 성공(최종 1.19초).
- `python -m alembic upgrade head`, `current`: **0004 (head)**.
- SQLite FK 활성화 상태의 마이그레이션 테스트: 기존 평가·리뷰 보존, IVD 테이블·증빙 연결 FK 확인, 0003으로 다운그레이드 후 재업그레이드 성공.
- `git diff --check`: 통과. Windows 줄바꿈 변환 안내만 발생.

테스트는 미확인 규제 근거의 실제 확정 거부, 다른 제품의 문서/증빙/개정본 연결 거부, 해당 없음의 사유 필수, 보완 종결 전 완료 409, 상태 전이 역순 거부, 증빙 개정 시 이전 패키지·다른 시장 보존, 초안 내보내기 스냅샷 보존, AI 초안 ID 및 수정 후 답변/근거 재검증을 포함합니다.

## 실제 HTTP 데모

`python -m scripts.demo_ivd` 성공. 아래 식별자는 첫 시연 결과이며 재실행하면 demo.json의 새 패키지 ID를 사용합니다.

- HIV EU v1: `b20d5c46-7352-4230-82d0-cd707e48a875`.
- HIV EU v2: `ab3cecba-5d77-466c-b5da-6244139c2c30`.
- COVID 국내 v1: `d9ce3691-8dfe-4642-a8af-d2df1eb6f10a`.
- HIV 국내 v1: `46b66090-156b-4430-a742-c505293c161b`.
- 최초 `EU-PERFORMANCE-001` 자료 누락 → 사유·담당자·기한 보완 요청.
- 성능 자료 **가상 메타데이터** 증빙 r1 등록, 성능평가 요약 문서 r2 등록. 새 패키지 v2에서 해당 요구사항 **재검토 필요** 확인.
- 5개 요구사항의 문서·증빙 개정본과 가상 내부 검토 적용 판단 기록.
- 보완 종결 전 내부 검토 완료 시도: **409**, unresolved에 열린 보완 표시.
- API 키 없이 변경 목록 확인과 수동 답변 저장 → **재검토 대기 → 재검토 → 종결** 확인.
- 최종 상태 **internal_complete**, 미해결 **0건**. 실제 규제 상태는 **규제 검토 필요** 유지. 가상 내부 검토가 실제 제품 등급·인허가 확정으로 표시되지 않음.
- 이전 v1의 문서/증빙 참조와 열린 보완 상태가 그대로인 것을 assert.
- HIV 국내와 COVID 국내의 문서·출처·검토 상태가 EU 보완 처리 후 바뀌지 않은 것을 assert.
- 화면에서 EU v2의 5개 충족 행, 문서 r2·증빙 r1, 보완 종결, JSON/Markdown 내보내기 링크를 확인. `ui-package.jpg`에 화면 증거 저장.

## 생성한 예시 문서

| 경로 | 상태 / 범위 |
|---|---|
| reports/ivd/hiv-eu-v1-draft.md 및 .json | EU 초안 v1, 누락·열린 보완 포함 |
| reports/ivd/hiv-eu-v2-reviewed.md 및 .json | EU 내부 검토 v2, 공식 출처 스냅샷·문서 개정본·증빙·보완/검토 이력 |
| reports/ivd/covid-kr-v1-draft.md 및 .json | 별도 국내 가상 기준 초안, 미확정·누락 포함 |
| reports/ivd/hiv-kr-v1-draft.md 및 .json | 동일 HIV 제품의 별도 국내 패키지, 증빙 재사용·시장 판단 분리 |
| reports/ivd/source-verification.json | 공식 확인 범위와 미확인 항목 |
| reports/ivd/demo.json | 패키지·증빙·보완 ID, 비교 결과, 409 확인, 과거 보존·격리 확인 |
| reports/ivd/ui-package.jpg | 브라우저 검증 화면 |

모든 가상 제품 내보내기에 **가상 제품 · 검토용 예시**가 표시됩니다. 초안도 상태와 미해결 항목을 포함해 내보냈고 HF 키 없이 동작했습니다.

## 공식 출처 대조 결과

1. [EUR-Lex 원문 32017R0746](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32017R0746): **Regulation (EU) 2017/746**의 번호와 IVD 법령 제목을 대조했습니다. 2017/745로 등록하지 않았습니다.
2. [확인한 통합문 02017R0746-20250110](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02017R0746-20250110): Annex II 1.1(a)/(c), Annex II 6, Annex I 20.2, Annex XIII 성능평가 참조를 확인했습니다. 확인일 2026-11-24, 문서 버전 2025-01-10 통합문으로 저장했습니다. 이는 법령 번호·제목·위치 확인이며 제품별 적용 판단 확정이 아닙니다.
3. [국가법령정보센터](https://www.law.go.kr/admRulLsInfoP.do?admRulSeq=2100000283814): **체외진단의료기기 허가ㆍ신고ㆍ심사 등에 관한 규정**, 제2026-58호, 시행 2026-08-10 제목·버전을 확인했습니다.
4. [식약처 공식 개정 공고](https://www.mfds.go.kr/law/board/boardDetail.do?brdId=data0008&menuKey=28&seq=15186): 같은 고시 번호·개정일과 제25~27조 사용적합성 자료 변경 설명을 확인했습니다.

### 미확인 / 범위 제한

- 국내 첨부 전문의 조항별 문구·별표 대조는 확보하지 못했습니다. 국내 공식 템플릿은 partial이며 적용 확정을 API에서 거부합니다. 로컬 국내 데모에는 별도 VIRTUAL-KR-001 가상 기준을 사용했습니다.
- HIV·COVID의 실제 국내/EU 분류, 제출 경로, 개별 적용/면제, 자가검사 여부, 모든 규제 문서 패키지의 완전성은 확정하지 않았습니다.
- 법령의 문서 제목과 일부 조항 확인을 실제 기술·성능 적합성 판단으로 사용하지 않았습니다.
- HF 실제 생성 호출은 미검증. 가짜 공급자로 스키마·문장별 ID·편집 후 저장 검증을 수행했습니다.
- Docker 실행 파일이 없어 PostgreSQL/Redis/RQ/Compose 실제 통합은 미검증. IVD API 자체는 SQLite 및 로컬 HTTP에서 실행했고 기존 워커 테스트를 함께 통과했습니다.
- 실제 파일 본문 업로드/파싱·전자서명·사용자 인증/권한·규제기관 제출·관리자의 DB 직접 변경 방지 트리거는 범위 밖입니다. 현재는 가상 메타데이터와 신뢰된 로컬 검토자 이름으로 동작합니다.
- ID 검증은 인용 범위를 확인하지만 AI 문장의 의미상 근거 충족·등록 자료의 진실성까지 증명하지 않습니다. 사람 검토가 필요합니다.

## 실행 명령

```bash
alembic upgrade head
QUEUE_MODE=thread uvicorn backend.main:app --host 127.0.0.1 --port 8000
# 다른 터미널
python -m scripts.demo_ivd
pytest tests -q
cd frontend
npm ci
npm run build
cd ..
python -m http.server 8080 --bind 127.0.0.1 --directory frontend/dist
```

PowerShell은 `$env:QUEUE_MODE='thread'`를 사용합니다. 화면은 `http://localhost:8080/?ivd=1`입니다.
