import pandas as pd
import numpy as np
import os
import torch
import pickle
from sentence_transformers import CrossEncoder
from tqdm import tqdm

# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------
BASE_DIR = os.path.expanduser('~/BaroLaw/autorag_eval/autorag_data')
WORK_DIR = os.path.expanduser('~/BaroLaw/autorag_eval/workspace')
CACHE_PATH = os.path.join(WORK_DIR, 'retrieval_cache.pkl')
QA_PATH = os.path.join(BASE_DIR, 'qa.parquet')
CORPUS_PATH = os.path.join(BASE_DIR, 'corpus.parquet')
OUTPUT_MD = os.path.expanduser('~/BaroLaw/autorag_eval/workspace/ai_performance_card.md')

def generate_performance_card():
    print("=" * 60)
    print("🔬 [AI 실전 성적표] Ko-Reranker 검증 데이터 생성 중...")
    print("=" * 60)

    # 1. 데이터 로드
    if not os.path.exists(CACHE_PATH):
        print("❌ 에러: retrieval_cache.pkl이 없습니다. eval_reranker.py를 먼저 실행해야 합니다.")
        return

    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)

    qa_df = pd.read_parquet(QA_PATH)
    corpus_df = pd.read_parquet(CORPUS_PATH)
    corpus_map = dict(zip(corpus_df['doc_id'], corpus_df['contents']))

    # 원본 쿼리 매핑용 (gt_id를 키로 사용)
    qa_df['gt_id'] = qa_df['retrieval_gt'].apply(lambda x: x[0][0])
    orig_query_map = dict(zip(qa_df['gt_id'], qa_df['query']))

    # 2. 리랭커 로드 (Ko-Reranker)
    print("🧠 리랭커 모델 로딩 (Dongjin-kr/ko-reranker)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    reranker = CrossEncoder("Dongjin-kr/ko-reranker", max_length=512, device=device)

    performance_rows = []

    # 3. 실전 테스트 (100건)
    print("📝 쿼리별 AI 답변(리랭킹 1위) 추출 중...")
    for item in tqdm(cache):
        hard_query = item['query']
        gt_ids = item['gt_ids']
        gt_target_id = gt_ids[0] # 첫 번째 정답 ID
        
        # 원본 쿼리 찾기
        orig_query = orig_query_map.get(gt_target_id, "정보 없음")
        
        # 리랭킹 수행
        candidate_texts = item['vector_texts']
        candidate_ids = item['vector_ids']
        
        pairs = [[hard_query, t] for t in candidate_texts]
        scores = reranker.predict(pairs)
        
        # 1등 결정
        top1_idx = np.argmax(scores)
        ai_choice_id = candidate_ids[top1_idx]
        ai_choice_text = candidate_texts[top1_idx]
        
        # 성공 여부 확인
        success = "✅ SUCCESS" if ai_choice_id == gt_target_id else "❌ FAIL"
        
        # 표에 들어갈 내용 정규화
        def clean(text):
            return ' '.join(text.replace('\n', ' ').replace('|', 'ㅣ').split())

        performance_rows.append({
            "Original": clean(orig_query),
            "Hard": clean(hard_query),
            "GT_Content": clean(corpus_map.get(gt_target_id, "없음"))[:100] + "...",
            "AI_Choice": clean(ai_choice_text)[:100] + "...",
            "Result": success
        })

    # 4. Markdown 파일 생성
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write('# 🏆 BaroLaw AI 실전 성적표 (Ko-Reranker 검증)\n\n')
        f.write('이 표는 **가혹 쿼리 100건**에 대해 AI(Ko-Reranker)가 실제로 정답 법령을 제대로 찾아냈는지 전수 조사한 결과입니다.\n\n')
        f.write('| ID | 원본 질문 (의도) | 변조된 질문 (Hard) | 정답 근거 (Ground Truth) | **AI의 실제 선택 (Top-1)** | **결과** |\n')
        f.write('| :--- | :--- | :--- | :--- | :--- | :--- |\n')
        
        for i, row in enumerate(performance_rows):
            f.write(f"| {i+1} | {row['Original']} | {row['Hard']} | {row['GT_Content']} | {row['AI_Choice']} | {row['Result']} |\n")

    print(f"\n✅ 성적표 생성 완료: {OUTPUT_MD}")

if __name__ == "__main__":
    generate_performance_card()
