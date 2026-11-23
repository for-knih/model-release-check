# 릴리스 검토 보고서

- 릴리스: 환불 품질 수정 후보 릴리스 검토 / 6bdbf0a4-2246-49a8-ad4d-e3845cd0fc5d
- 결과 구분: 시나리오 데모 (고정 예측)
- 시스템 판정: passed
- 일반 승인 가능: True

| 요구사항 | 버전 | 정책 버전 | 적용 기준 | 관측값 | 판정 | 근거 실행 |
|---|---:|---|---|---|---|---|
| REQ-REFUND-001 | 1 | POL-REFUND-001 v1 | {&#x27;refund_min_recall&#x27;: 0.85, &#x27;refund_max_drop&#x27;: 0.05} | {&#x27;baseline_refund_recall&#x27;: 1.0, &#x27;candidate_refund_recall&#x27;: 1.0, &#x27;refund_drop&#x27;: 0.0, &#x27;refund_support&#x27;: 5} | 통과 | 2dcd94db-222a-4adb-ac12-c5f584887c6e |
- 대표 위반 사례 ID: 없음

## 최초 실패 실행
- 실행 ID: 9877041d-58ac-4f04-8cdf-3abc4f4113cd
- 데이터셋 버전: addfc455911ddbaf1f0e6a36f880001d595dad778ec94ebeb819199070366235
- 모델: fixed-scenario-v1 → fixed-scenario-v1
- 커밋: scenario-original-demo
- 유효 모델 설정: {&#x27;dataset_id&#x27;: &#x27;9e922213-7877-4276-ad42-ff863e0e7d68&#x27;, &#x27;dataset_version&#x27;: &#x27;addfc455911ddbaf1f0e6a36f880001d595dad778ec94ebeb819199070366235&#x27;, &#x27;mode&#x27;: &#x27;scenario&#x27;, &#x27;commit_sha&#x27;: &#x27;scenario-original-demo&#x27;, &#x27;policy&#x27;: {&#x27;refund_min_recall&#x27;: 0.85, &#x27;refund_max_drop&#x27;: 0.05}, &#x27;evaluation_implementation&#x27;: &#x27;f2419b6da59a6291363d3c501c901bea395ac30b6d327946d7ddcbb7f7bc85c0&#x27;, &#x27;baseline_config&#x27;: {&#x27;adapter&#x27;: &#x27;fixed-scenario&#x27;}, &#x27;candidate_config&#x27;: {&#x27;adapter&#x27;: &#x27;fixed-scenario&#x27;, &#x27;variant&#x27;: &#x27;original&#x27;}, &#x27;scenario_hash&#x27;: &#x27;b98a5d2e2d6135b7c224e03c76a43751177b09fbcd7697dd466f68a25d39ae60&#x27;, &#x27;requirements&#x27;: [{&#x27;id&#x27;: 1, &#x27;identifier&#x27;: &#x27;REQ-REFUND-001&#x27;, &#x27;version&#x27;: 1, &#x27;title&#x27;: &#x27;환불 문의 품질 보존&#x27;, &#x27;verification_condition&#x27;: &#x27;후보 환불 재현율 85% 이상, 기준 대비 하락폭 5%p 이하&#x27;, &#x27;owner&#x27;: &#x27;AI 백엔드 담당자&#x27;, &#x27;status&#x27;: &#x27;active&#x27;, &#x27;mandatory&#x27;: True, &#x27;policy&#x27;: {&#x27;identifier&#x27;: &#x27;POL-REFUND-001&#x27;, &#x27;version&#x27;: 1, &#x27;config&#x27;: {&#x27;refund_min_recall&#x27;: 0.85, &#x27;refund_max_drop&#x27;: 0.05}}}]}
- 주요 지표: {&#x27;baseline&#x27;: {&#x27;accuracy&#x27;: 0.6, &#x27;macro_f1&#x27;: 0.611111111111111, &#x27;classes&#x27;: {&#x27;배송&#x27;: {&#x27;recall&#x27;: 0.4, &#x27;support&#x27;: 5}, &#x27;환불&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;결제&#x27;: {&#x27;recall&#x27;: 0.4, &#x27;support&#x27;: 5}, &#x27;기타&#x27;: {&#x27;recall&#x27;: 0.6, &#x27;support&#x27;: 5}}}, &#x27;candidate&#x27;: {&#x27;accuracy&#x27;: 0.85, &#x27;macro_f1&#x27;: 0.8465909090909092, &#x27;classes&#x27;: {&#x27;배송&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;환불&#x27;: {&#x27;recall&#x27;: 0.6, &#x27;support&#x27;: 5}, &#x27;결제&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;기타&#x27;: {&#x27;recall&#x27;: 0.8, &#x27;support&#x27;: 5}}}, &#x27;recommendation&#x27;: &#x27;hold&#x27;, &#x27;reasons&#x27;: [&#x27;환불 재현율 60.0% &lt; 최소 85.0%&#x27;, &#x27;환불 재현율 하락 40.0%p &gt; 허용 5.0%p&#x27;]}

## 수정 후보 실행
- 실행 ID: 2dcd94db-222a-4adb-ac12-c5f584887c6e
- 데이터셋 버전: addfc455911ddbaf1f0e6a36f880001d595dad778ec94ebeb819199070366235
- 모델: fixed-scenario-v1 → fixed-scenario-repaired-v1
- 커밋: scenario-repaired-demo
- 유효 모델 설정: {&#x27;dataset_id&#x27;: &#x27;9e922213-7877-4276-ad42-ff863e0e7d68&#x27;, &#x27;dataset_version&#x27;: &#x27;addfc455911ddbaf1f0e6a36f880001d595dad778ec94ebeb819199070366235&#x27;, &#x27;mode&#x27;: &#x27;scenario&#x27;, &#x27;commit_sha&#x27;: &#x27;scenario-repaired-demo&#x27;, &#x27;policy&#x27;: {&#x27;refund_min_recall&#x27;: 0.85, &#x27;refund_max_drop&#x27;: 0.05}, &#x27;evaluation_implementation&#x27;: &#x27;f2419b6da59a6291363d3c501c901bea395ac30b6d327946d7ddcbb7f7bc85c0&#x27;, &#x27;baseline_config&#x27;: {&#x27;adapter&#x27;: &#x27;fixed-scenario&#x27;}, &#x27;candidate_config&#x27;: {&#x27;adapter&#x27;: &#x27;fixed-scenario&#x27;, &#x27;variant&#x27;: &#x27;repaired&#x27;}, &#x27;scenario_hash&#x27;: &#x27;7406cf208ebe8be09670bd5cb6687040050c782a5307a53e8fa14a3eb29309f9&#x27;, &#x27;requirements&#x27;: [{&#x27;id&#x27;: 1, &#x27;identifier&#x27;: &#x27;REQ-REFUND-001&#x27;, &#x27;version&#x27;: 1, &#x27;title&#x27;: &#x27;환불 문의 품질 보존&#x27;, &#x27;verification_condition&#x27;: &#x27;후보 환불 재현율 85% 이상, 기준 대비 하락폭 5%p 이하&#x27;, &#x27;owner&#x27;: &#x27;AI 백엔드 담당자&#x27;, &#x27;status&#x27;: &#x27;active&#x27;, &#x27;mandatory&#x27;: True, &#x27;policy&#x27;: {&#x27;identifier&#x27;: &#x27;POL-REFUND-001&#x27;, &#x27;version&#x27;: 1, &#x27;config&#x27;: {&#x27;refund_min_recall&#x27;: 0.85, &#x27;refund_max_drop&#x27;: 0.05}}}]}
- 주요 지표: {&#x27;baseline&#x27;: {&#x27;accuracy&#x27;: 0.6, &#x27;macro_f1&#x27;: 0.611111111111111, &#x27;classes&#x27;: {&#x27;배송&#x27;: {&#x27;recall&#x27;: 0.4, &#x27;support&#x27;: 5}, &#x27;환불&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;결제&#x27;: {&#x27;recall&#x27;: 0.4, &#x27;support&#x27;: 5}, &#x27;기타&#x27;: {&#x27;recall&#x27;: 0.6, &#x27;support&#x27;: 5}}}, &#x27;candidate&#x27;: {&#x27;accuracy&#x27;: 0.95, &#x27;macro_f1&#x27;: 0.9494949494949495, &#x27;classes&#x27;: {&#x27;배송&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;환불&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;결제&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;기타&#x27;: {&#x27;recall&#x27;: 0.8, &#x27;support&#x27;: 5}}}, &#x27;recommendation&#x27;: &#x27;approve&#x27;, &#x27;reasons&#x27;: []}

## 동일 조건 비교
{&#x27;allowed&#x27;: True, &#x27;restriction_reasons&#x27;: [], &#x27;deltas&#x27;: {&#x27;accuracy&#x27;: 0.09999999999999998, &#x27;refund_recall&#x27;: 0.4, &#x27;accuracy_improved&#x27;: True, &#x27;refund_recall_improved&#x27;: True}}

## 재현 사례 / 수정 미사용 사례
- 원본 9877041d-58ac-4f04-8cdf-3abc4f4113cd / eval-008 → 대상 버전 addfc455911ddbaf1f0e6a36f880001d595dad778ec94ebeb819199070366235 / eval-008: 기타 → 환불 (passed)
- 원본 9877041d-58ac-4f04-8cdf-3abc4f4113cd / eval-009 → 대상 버전 addfc455911ddbaf1f0e6a36f880001d595dad778ec94ebeb819199070366235 / eval-009: 기타 → 환불 (passed)
{&#x27;label&#x27;: &#x27;수정에 사용하지 않은 사례 부분집합 · 독립 평가 세트 아님&#x27;, &#x27;count&#x27;: 18, &#x27;metrics&#x27;: {&#x27;accuracy&#x27;: 0.9444444444444444, &#x27;macro_f1&#x27;: 0.9494949494949495, &#x27;classes&#x27;: {&#x27;배송&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;환불&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 3}, &#x27;결제&#x27;: {&#x27;recall&#x27;: 1.0, &#x27;support&#x27;: 5}, &#x27;기타&#x27;: {&#x27;recall&#x27;: 0.8, &#x27;support&#x27;: 5}}}}
- 독립 평가 세트: {&#x27;status&#x27;: &#x27;unverified&#x27;, &#x27;label&#x27;: &#x27;독립 평가 세트 미검증&#x27;, &#x27;reasons&#x27;: [&#x27;별도 완료된 holdout_run_id가 없습니다&#x27;], &#x27;run&#x27;: None}

## 검토자 최종 결정
- approve / 릴리스 검토자 / 동일 세트·정책에서 환불 60%→100%, 재현 사례 2건 통과 확인. 시나리오 데모 검토 기록. / 근거 실행 2dcd94db-222a-4adb-ac12-c5f584887c6e

## 승인 제한
