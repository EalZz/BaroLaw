import pandas as pd
import numpy as np
import os
import torch
from sentence_transformers import SentenceTransformer, util
from rank_bm25 import BM25Okapi
import time

# ---------------------------------------------------------
# 설정 및 경로 (격리된 환경 유지)
# ---------------------------------------------------------
BASE_DIR = os.path.expanduser("~/BaroLaw/autorag_eval/autorag_data")
CORPUS_PATH = os.path.join(BASE_DIR, "corpus.parquet")
QA_PATH = os.path.join(BASE_DIR, "qa_hard.parquet")
MODEL_NAME = "jhgan/ko-sroberta-multitask"
TOP_K = 5

def dcg_at_k(r, k):
    r = np.asfarray(r)[:k]
    if r.size:
        return np.sum(r / np.log2(np.arange(2, r.size + 2)))
    return 0.

def ndcg_at_k(r, k):
    idcg = dcg_at_k(sorted(r, reverse=True), k)
    if not idcg:
        return 0.
    return dcg_at_k(r, k) / idcg

def evaluate():
    print("\n" + "="*50)
    print("🚀 [BaroLaw] 로컬 검색 성능 정밀 평가 시작")
    print("="*50)

    # 1. 데이터 로드
    print(f"📦 데이터 로딩 중: {CORPUS_PATH}...")
    corpus_df = pd.read_parquet(CORPUS_PATH)
    qa_df = pd.read_parquet(QA_PATH)
    
    documents = corpus_df['contents'].tolist()
    doc_ids = corpus_df['doc_id'].tolist()
    
    print(f"✅ 코퍼스: {len(documents)}건 / 테스트 QA: {len(qa_df)}건 로드 완료.")

    # 2. BM25 (Lexical) 준비
    print("📝 BM25 인덱싱 중 (키워드 매칭)...")
    tokenized_corpus = [doc.split() for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)

    # 3. Vector (Semantic) 준비
    print(f"🧠 Vector 임베딩 모델 로딩 중 ({MODEL_NAME})...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)
    corpus_embeddings = model.encode(documents, convert_to_tensor=True, show_progress_bar=True)

    # 4. 평가 루프
    results = {
        "BM25": {"ndcg": [], "recall": []},
        "Vector": {"ndcg": [], "recall": []},
        "Hybrid": {"ndcg": [], "recall": []}
    }

    print("\n📊 알고리즘별 성능 측정 중 (NDCG, Recall)...")
    
    for _, row in qa_df.iterrows():
        query = row['query']
        gt_ids = row['retrieval_gt'][0] # 리스트의 첫 번째 세트 사용

        # --- BM25 검색 ---
        tokenized_query = query.split()
        bm25_scores = bm25.get_scores(tokenized_query)
        bm25_top_indices = np.argsort(bm25_scores)[::-1][:TOP_K]
        bm25_results = [doc_ids[i] for i in bm25_top_indices]

        # --- Vector 검색 ---
        query_embedding = model.encode(query, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
        vector_top_indices = torch.topk(cos_scores, k=TOP_K).indices.cpu().numpy()
        vector_results = [doc_ids[i] for i in vector_top_indices]

        # --- Hybrid (RRF) 검색 ---
        # 간단한 Reciprocal Rank Fusion 구현
        rrf_scores = {}
        for rank, d_id in enumerate(bm25_results):
            rrf_scores[d_id] = rrf_scores.get(d_id, 0) + 1 / (60 + rank + 1)
        for rank, d_id in enumerate(vector_results):
            rrf_scores[d_id] = rrf_scores.get(d_id, 0) + 1 / (60 + rank + 1)
        
        hybrid_results = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:TOP_K]

        # --- 메트릭 계산 ---
        for name, res_ids in [("BM25", bm25_results), ("Vector", vector_results), ("Hybrid", hybrid_results)]:
            # Relevance score (1 if in GT, 0 otherwise)
            rel = [1 if d_id in gt_ids else 0 for d_id in res_ids]
            
            # NDCG
            results[name]["ndcg"].append(ndcg_at_k(rel, TOP_K))
            # Recall
            recall = sum(rel) / len(gt_ids) if len(gt_ids) > 0 else 0
            results[name]["recall"].append(recall)

    # 5. 최종 리포트 출력
    print("\n" + "🏆 [최종 검색 성능 리더보드] (Top-5 기준)")
    print("-" * 60)
    print(f"{'알고리즘':<15} | {'NDCG':<15} | {'Recall':<15}")
    print("-" * 60)
    for name in ["BM25", "Vector", "Hybrid"]:
        avg_ndcg = np.mean(results[name]["ndcg"])
        avg_recall = np.mean(results[name]["recall"])
        print(f"{name:<15} | {avg_ndcg:<15.4f} | {avg_recall:<15.4f}")
    print("-" * 60)
    print("\n✅ 분석 완료. 어떤 알고리즘이 우리 시스템에 가장 적합할까요?")

if __name__ == "__main__":
    evaluate()
