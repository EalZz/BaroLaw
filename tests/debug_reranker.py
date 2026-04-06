
from sentence_transformers import CrossEncoder
import torch

try:
    model = CrossEncoder('Dongjin-kr/ko-reranker', device='cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Model loaded on {model.device}")
except Exception as e:
    print(f"Error loading model: {e}")
    exit(1)

# Case 1: Insurance Fraud (FRAUD_07_S)
query1 = "보험금을 타내려고 고의로 교통사고를 낸 사람을 신고하고 싶습니다."
doc1 = "보험사기방지 특별법 제8조(보험사기죄) 보험사기행위로 보험금을 취득하거나 제3자에게 보험금을 취득하게 한 자는 10년 이하의 징역 또는 5천만원 이하의 벌금에 처한다."

# Case 2: Used Car Mileage (FRAUD_10_S)
query2 = "중고차 주행거리 조작해서 판 딜러를 상대로 환불받고 싶어요."
doc2 = "형법 제347조(사기) ①사람을 기망하여 재물의 교부를 받거나 재산상의 이익을 취득한 자는 10년 이하의 징역 또는 2천만원 이하의 벌금에 처한다."
doc2_wrong = "자동차손해배상 보장법 제6조(의무보험 미가입자에 대한 조치 등) ① 시장·군수·구청장은 의무보험에 가입하지 아니한 자동차를 운행하는 자에게 그 자동차의 운행 정지를 명할 수 있다."

pairs = [
    [query1, doc1],
    [query2, doc2],
    [query2, doc2_wrong]
]

scores = model.predict(pairs)
print(f"Scores: {scores}")
