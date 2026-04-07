import os
import sys
import pandas as pd
from typing import List, Dict, Any

# backend 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.rag import LegalRAGPipeline, HybridRRF, Reranker, ContextBuilder

def debug_search(query_info):
    print(f"\n{'='*60}")
    print(f"CASE: {query_info['id']}")
    print(f"Query: {query_info['query']}")
    print(f"LLM Keywords: {query_info['keywords']}")
    print(f"Category: {query_info['category']}")
    print(f"{'='*60}")

    pipeline = LegalRAGPipeline()
    if not pipeline.initialized:
        pipeline.initialize()

    # 1. BM25 Search
    bm25_res = pipeline.bm25_retriever.search(query_info['query'])
    print(f"\n[BM25 Top 5]")
    for idx, score in bm25_res[:5]:
        item = pipeline.corpus[idx]
        meta = item.get('metadata', {})
        print(f" - {str(meta.get('law_name') or '')} ({str(meta.get('article') or '')}): {score:.4f}")

    # 2. Vector Search
    vector_res = pipeline.vector_retriever.search(query_info['query'])
    print(f"\n[Vector Top 5]")
    for idx, score in vector_res[:5]:
        item = pipeline.corpus[idx]
        meta = item.get('metadata', {})
        print(f" - {str(meta.get('law_name') or '')} ({str(meta.get('article') or '')}): {score:.4f}")

    # 3. Hybrid Fusion (Top 30 candidates for Reranking)
    fused_indices = pipeline.rrf_fusion.fuse(bm25_res, vector_res)
    print(f"\n[Hybrid Fused Top 30 Candidates]")
    target_found = False
    for i, idx in enumerate(fused_indices[:30]):
        item = pipeline.corpus[idx]
        meta = item.get('metadata', {})
        law_name = str(meta.get('law_name') or '')
        art = str(meta.get('article') or '')
        marker = ""
        if "형법" in law_name and "347" in art:
            marker = " <--- TARGET FOUND!"
            target_found = True
        print(f" {i+1:2d}. {law_name} ({art}){marker}")
    
    if not target_found:
        print(f"\n❌ ALERT: '형법 제347조' NOT FOUND in Top 30 candidates!")
        # 100위까지 더 뒤져보기
        for i, idx in enumerate(fused_indices[30:100]):
            item = pipeline.corpus[idx]
            meta = item.get('metadata', {})
            law_name = str(meta.get('law_name') or '')
            art = str(meta.get('article') or '')
            if "형법" in law_name and "347" in art:
                print(f" -> Found at Rank {i+31}: {law_name} ({art})")
                target_found = True
                break
        if not target_found:
            print(" -> NOT FOUND even in Top 100 candidates.")

    # 4. Reranking
    reranked_res = pipeline.reranker.rerank(query_info['query'], pipeline.corpus, fused_indices)
    print(f"\n[Reranked results (Before Boosting)]")
    for i, (idx, score) in enumerate(reranked_res[:15]):
        item = pipeline.corpus[idx]
        meta = item.get('metadata', {})
        law_name = str(meta.get('law_name') or '')
        art = str(meta.get('article') or '')
        marker = ""
        if "형법" in law_name and "347" in art:
            marker = " <--- TARGET FOUND!"
        print(f" {i+1:2d}. {law_name} ({art}): {score:.4f}{marker}")

    # 5. Boosting & Final Context Building
    final_statutes = pipeline.context_builder.build(
        pipeline.corpus, 
        reranked_res, 
        pipeline.category_law_boost, 
        query_info['category'], 
        [query_info['category']], 
        query_info['keywords'], 
        pipeline.domain_shield_config
    )

    print(f"\n[Final Retrieved List (After Boosting)]")
    for i, s in enumerate(final_statutes[:10]):
        law_name = s['law_name']
        art = s['article']
        print(f" {i+1:d}. {law_name} ({art})")

if __name__ == "__main__":
    cases = [
        {
            "id": "FRAUD_10_S",
            "query": "중고차 주행거리 조작해서 판 딜러를 상대로 환불받고 싶어요. 사기 중고차 주행거리 조작 형법",
            "keywords": ["사기", "중고차 주행거리 조작", "형법"],
            "category": "FRAUD"
        },
        {
            "id": "FRAUD_11_S",
            "query": "취업 시켜준다고 수수료 명목으로 돈을 받아 가더니 연락이 안 됩니다. 금전 편취 사기 수수료 요구",
            "keywords": ["금전 편취", "사기", "수수료 요구"],
            "category": "FRAUD"
        },
        {
            "id": "FRAUD_12_S",
            "query": "명의 빌려주면 돈 준다고 해서 빌려줬는데 제 명의로 대출이 잔뜩 생겼어요. 명의대여 사기 형법",
            "keywords": ["명의대여", "사기", "형법"],
            "category": "FRAUD"
        }
    ]

    for case in cases:
        debug_search(case)
