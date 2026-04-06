import pandas as pd
import numpy as np
import os
import torch
import requests
import pickle
from sentence_transformers import SentenceTransformer, util, CrossEncoder
from rank_bm25 import BM25Okapi
from tqdm import tqdm

# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------
BASE_DIR = os.path.expanduser("~/BaroLaw/autorag_eval/autorag_data")
WORK_DIR = os.path.expanduser("~/BaroLaw/autorag_eval/workspace")
CORPUS_PATH = os.path.join(BASE_DIR, "corpus.parquet")
QA_PATH = os.path.join(BASE_DIR, "qa_hard.parquet")
CACHE_PATH = os.path.join(WORK_DIR, "retrieval_cache.pkl")
EMBED_MODEL = "jhgan/ko-sroberta-multitask"
INITIAL_TOP_K = 10
FINAL_TOP_K = 5
OLLAMA_URL = "http://localhost:11434/api/generate"

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

def calc_metrics(result_ids, gt_ids, k):
    rel = [1 if d_id in gt_ids else 0 for d_id in result_ids[:k]]
    ndcg = ndcg_at_k(rel, k)
    recall = sum(rel) / len(gt_ids) if len(gt_ids) > 0 else 0
    return ndcg, recall

def hybrid_rrf(bm25_ids, vector_ids, bm25_w=0.5, vector_w=0.5, top_k=5):
    rrf = {}
    for rank, d_id in enumerate(bm25_ids):
        rrf[d_id] = rrf.get(d_id, 0) + bm25_w / (60 + rank + 1)
    for rank, d_id in enumerate(vector_ids):
        rrf[d_id] = rrf.get(d_id, 0) + vector_w / (60 + rank + 1)
    return sorted(rrf.keys(), key=lambda x: rrf[x], reverse=True)[:top_k]

# =========================================================
# PHASE 1: 1차 검색 결과 캐싱 (GPU 사용 후 해제)
# =========================================================
def phase1_cache():
    print("=" * 60)
    print("[Phase 1] 1차 검색 결과 사전 캐싱 (GPU)")
    print("=" * 60)

    corpus_df = pd.read_parquet(CORPUS_PATH)
    qa_df = pd.read_parquet(QA_PATH)
    documents = corpus_df['contents'].tolist()
    doc_ids = corpus_df['doc_id'].tolist()
    print(f"  코퍼스: {len(documents)}건 / QA: {len(qa_df)}건")

    # BM25
    print("  BM25 인덱싱...")
    bm25 = BM25Okapi([doc.split() for doc in documents])

    # Vector
    print(f"  임베딩 모델 로딩 ({EMBED_MODEL})...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(EMBED_MODEL, device=device)
    print("  코퍼스 임베딩 중...")
    corpus_emb = model.encode(documents, convert_to_tensor=True, show_progress_bar=True)

    cache = []
    print("  쿼리별 1차 검색 결과 계산 중...")
    for _, row in tqdm(qa_df.iterrows(), total=len(qa_df)):
        query = row['query']
        gt_ids = row['retrieval_gt'][0]

        # Vector Top-10
        q_emb = model.encode(query, convert_to_tensor=True)
        cos = util.cos_sim(q_emb, corpus_emb)[0]
        v_idx = torch.topk(cos, k=INITIAL_TOP_K).indices.cpu().numpy()
        v_ids = [doc_ids[i] for i in v_idx]
        v_texts = [documents[i] for i in v_idx]

        # BM25 Top-10
        bm25_scores = bm25.get_scores(query.split())
        b_idx = np.argsort(bm25_scores)[::-1][:INITIAL_TOP_K]
        b_ids = [doc_ids[i] for i in b_idx]

        cache.append({
            "query": query, "gt_ids": gt_ids,
            "vector_ids": v_ids, "vector_texts": v_texts,
            "bm25_ids": b_ids
        })

    # GPU 메모리 해제
    del model, corpus_emb
    torch.cuda.empty_cache()
    print("  GPU 메모리 해제 완료.")

    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"  캐시 저장됨: {CACHE_PATH}\n")
    return cache

# =========================================================
# PHASE 2: 리랭커 실험 (CPU 위주, 순차 실행)
# =========================================================
def phase2_rerank(cache):
    print("=" * 60)
    print("[Phase 2] 리랭커 3종 + 하이브리드 가중치 비교")
    print("=" * 60)

    results = {
        "Vector Only (Baseline)": {"ndcg": [], "recall": []},
        "Hybrid 5:5 (Baseline)": {"ndcg": [], "recall": []},
        "Hybrid 2:8": {"ndcg": [], "recall": []},
        "Hybrid 3:7": {"ndcg": [], "recall": []},
        "Hybrid 1:9": {"ndcg": [], "recall": []},
    }

    # --- Baseline + Hybrid (빠름) ---
    print("\n[2-1] Baseline + Hybrid 가중치 실험...")
    for item in tqdm(cache, desc="Baseline+Hybrid"):
        gt = item["gt_ids"]
        v_ids = item["vector_ids"]
        b_ids = item["bm25_ids"]

        n, r = calc_metrics(v_ids, gt, FINAL_TOP_K)
        results["Vector Only (Baseline)"]["ndcg"].append(n)
        results["Vector Only (Baseline)"]["recall"].append(r)

        for name, bw, vw in [("Hybrid 5:5 (Baseline)", 0.5, 0.5),
                              ("Hybrid 2:8", 0.2, 0.8),
                              ("Hybrid 3:7", 0.3, 0.7),
                              ("Hybrid 1:9", 0.1, 0.9)]:
            h = hybrid_rrf(b_ids, v_ids, bw, vw, FINAL_TOP_K)
            n, r = calc_metrics(h, gt, FINAL_TOP_K)
            results[name]["ndcg"].append(n)
            results[name]["recall"].append(r)

    # --- 리랭커 A: Ko-Reranker ---
    print("\n[2-2] 실험 A: Ko-Reranker (Dongjin-kr/ko-reranker)...")
    results["Vector + Ko-Reranker"] = {"ndcg": [], "recall": []}
    try:
        ko_reranker = CrossEncoder("Dongjin-kr/ko-reranker", max_length=512)
        for item in tqdm(cache, desc="Ko-Reranker"):
            pairs = [[item["query"], t] for t in item["vector_texts"]]
            scores = ko_reranker.predict(pairs)
            ranked = np.argsort(scores)[::-1][:FINAL_TOP_K]
            reranked_ids = [item["vector_ids"][i] for i in ranked]
            n, r = calc_metrics(reranked_ids, item["gt_ids"], FINAL_TOP_K)
            results["Vector + Ko-Reranker"]["ndcg"].append(n)
            results["Vector + Ko-Reranker"]["recall"].append(r)
        del ko_reranker
    except Exception as e:
        print(f"  Ko-Reranker 실패: {e}")

    # --- 리랭커 C: BGE-Reranker-large ---
    print("\n[2-3] 실험 C: BGE-Reranker-large...")
    results["Vector + BGE-Reranker"] = {"ndcg": [], "recall": []}
    try:
        bge_reranker = CrossEncoder("BAAI/bge-reranker-large", max_length=512)
        for item in tqdm(cache, desc="BGE-Reranker"):
            pairs = [[item["query"], t] for t in item["vector_texts"]]
            scores = bge_reranker.predict(pairs)
            ranked = np.argsort(scores)[::-1][:FINAL_TOP_K]
            reranked_ids = [item["vector_ids"][i] for i in ranked]
            n, r = calc_metrics(reranked_ids, item["gt_ids"], FINAL_TOP_K)
            results["Vector + BGE-Reranker"]["ndcg"].append(n)
            results["Vector + BGE-Reranker"]["recall"].append(r)
        del bge_reranker
    except Exception as e:
        print(f"  BGE-Reranker 실패: {e}")

    # --- 리랭커 B: Gemma 2 LLM ---
    print("\n[2-4] 실험 B: Gemma 2 LLM Rerank (가장 느림)...")
    results["Vector + Gemma2 Rerank"] = {"ndcg": [], "recall": []}
    for item in tqdm(cache, desc="Gemma2 Rerank"):
        scored = []
        for i, doc in enumerate(item["vector_texts"]):
            prompt = f"다음 질문과 문서의 관련성을 0~10 숫자 하나로만 답하세요.\n질문: {item['query']}\n문서: {doc[:200]}\n점수:"
            try:
                resp = requests.post(OLLAMA_URL, json={
                    "model": "gemma2", "prompt": prompt, "stream": False,
                    "options": {"num_predict": 5, "temperature": 0.0}
                }, timeout=15)
                text = resp.json().get('response', '0').strip() if resp.status_code == 200 else '0'
                score = float(''.join(c for c in text if c.isdigit() or c == '.') or '0')
            except:
                score = 0
            scored.append((item["vector_ids"][i], score))
        scored.sort(key=lambda x: x[1], reverse=True)
        reranked_ids = [s[0] for s in scored[:FINAL_TOP_K]]
        n, r = calc_metrics(reranked_ids, item["gt_ids"], FINAL_TOP_K)
        results["Vector + Gemma2 Rerank"]["ndcg"].append(n)
        results["Vector + Gemma2 Rerank"]["recall"].append(r)

    # =====================================================
    # 최종 출력
    # =====================================================
    print("\n" + "=" * 70)
    print("🏆 [리랭커 + 하이브리드 종합 리더보드] (가혹 쿼리 100건, Top-5)")
    print("=" * 70)
    print(f"{'실험명':<30} | {'NDCG':<10} | {'Recall':<10}")
    print("-" * 70)
    for name in results:
        if results[name]["ndcg"]:
            avg_n = np.mean(results[name]["ndcg"])
            avg_r = np.mean(results[name]["recall"])
            print(f"{name:<30} | {avg_n:<10.4f} | {avg_r:<10.4f}")
    print("-" * 70)

    # 파일 저장
    rpath = os.path.join(WORK_DIR, "reranker_results.txt")
    with open(rpath, "w", encoding="utf-8") as f:
        f.write("=== [BaroLaw] 리랭커 + 하이브리드 종합 리더보드 ===\n\n")
        f.write(f"{'실험명':<30} | {'NDCG':<10} | {'Recall':<10}\n")
        f.write("-" * 70 + "\n")
        for name in results:
            if results[name]["ndcg"]:
                f.write(f"{name:<30} | {np.mean(results[name]['ndcg']):<10.4f} | {np.mean(results[name]['recall']):<10.4f}\n")
    print(f"\n📄 결과 저장: {rpath}")

# =========================================================
if __name__ == "__main__":
    if os.path.exists(CACHE_PATH):
        print("📂 기존 캐시 발견. 로딩 중...")
        with open(CACHE_PATH, "rb") as f:
            cache = pickle.load(f)
    else:
        cache = phase1_cache()

    phase2_rerank(cache)
