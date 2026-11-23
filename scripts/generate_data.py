"""Handwritten synthetic inquiries. No evaluation text is used for fitting."""
import csv
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / 'data'
ROOT.mkdir(exist_ok=True)
train = {
 '배송': ['주문한 물건 언제 도착하나요', '택배 운송장 번호 알려 주세요', '배송 출발은 언제 되나요', '상품이 아직 오지 않았어요', '주소를 바꾸고 싶습니다', '수령 장소 변경 부탁드립니다', '오늘 출고 가능한가요', '배달 기사님 연락처 궁금합니다', '주문 물품이 며칠째 이동하지 않아요', '도착 예정일 확인 부탁드립니다', '집 앞에 놓아 주세요', '상품 발송 일정 알려주세요'],
 '환불': ['환불 신청하고 싶습니다', '반품 접수 부탁드립니다', '돈을 돌려받고 싶어요', '취소한 금액 언제 돌아오나요', '구매한 상품을 반납하겠습니다', '불량 제품 반환 절차 알려주세요', '돌려보낸 물건 금액 입금해주세요', '주문 취소 후 돈이 안 들어와요', '반품 비용이 얼마인가요', '환불 금액 확인해주세요', '사이즈가 안 맞아서 반품합니다', '구매를 철회하고 싶습니다'],
 '결제': ['결제 오류가 납니다', '카드 승인이 안 됩니다', '영수증 발급 부탁드립니다', '현금영수증 신청합니다', '계좌 이체 입금 확인해주세요', '중복으로 금액이 빠져나갔어요', '신용카드 할부 가능한가요', '주문 대금을 지불하고 싶어요', '간편 결제 비밀번호 오류입니다', '카드 등록 방법이 궁금합니다', '무통장 입금 계좌 알려주세요', '결제 수단 변경할 수 있나요'],
 '기타': ['회원 탈퇴 어떻게 하나요', '비밀번호를 잊어버렸어요', '상품 색상 종류가 궁금합니다', '적립금 사용 방법 알려주세요', '쿠폰 적용 조건은 무엇인가요', '매장 영업 시간 알려주세요', '회원 정보 수정하고 싶습니다', '제품 재질이 무엇인가요', '세탁 방법이 궁금해요', '사이즈 표를 보고 싶어요', '앱 로그인에 문제가 있어요', '선물 포장 가능한가요']}
evaluation = [
 ('배송','배송 상태 확인 부탁해요'),('배송','택배가 다른 집으로 갔어요'),('배송','내일 물건이 도착할까요'),('배송','출고 날짜를 알려 주세요'),('배송','수령 주소를 수정하려고 해요'),
 ('환불','환불 접수 후 진행 상황이 궁금해요'),('환불','반품한 상품의 돈이 안 왔어요'),('환불','환불 처리는 며칠 걸리나요'),('환불','반품 수거를 신청할게요'),('환불','환불 금액을 확인하고 싶어요'),
 ('결제','결제가 두 번 되었어요'),('결제','카드로 금액이 승인되지 않아요'),('결제','현금영수증 발행이 필요해요'),('결제','무통장 입금이 확인되었나요'),('결제','할부 개월 수를 바꾸고 싶어요'),
 ('기타','비밀번호 초기화 링크 보내주세요'),('기타','제품 원단이 면인가요'),('기타','로그인 오류를 해결해주세요'),('기타','쿠폰 유효 기간 알려 주세요'),('기타','선물용 포장을 추가해주세요')]
def write(name, rows):
 with (ROOT/name).open('w',encoding='utf-8',newline='') as f:
  w=csv.writer(f);w.writerow(['case_id','text','expected_label']);w.writerows(rows)
write('train.csv', [(f'train-{i:03}',text,label) for i,(label,text) in enumerate(( (l,t) for l, texts in train.items() for t in texts),1)])
write('evaluation.csv',[(f'eval-{i:03}',text,label) for i,(label,text) in enumerate(evaluation,1)])
# Baseline 12/20; candidate 17/20. Two refund regressions plus one shared error.
baseline_wrong={3,4,5,13,14,15,18,20}
candidate_wrong={8,9,20}
fixture={}
for i,(label,text) in enumerate(evaluation,1):
 wrong='기타' if label!='기타' else '배송'
 fixture[f'eval-{i:03}']={'baseline':wrong if i in baseline_wrong else label,'candidate':wrong if i in candidate_wrong else label}
(ROOT/'scenario.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2),encoding='utf-8')
