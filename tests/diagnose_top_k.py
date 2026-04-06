import json
import os
import sys
import pandas as pd
import numpy as np

# backend 경로 추가 (상대 경로 기준)
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from rag import LegalRAGPipeline, load_rag_config

# 진단 대상 (실패한 12건)
FAILED_CASES = [
    "FRAUD_12_S", "FRAUD_30_M", 
    "CRIMINAL_28_M", 
    "REAL_ESTATE_02_S", "REAL_ESTATE_16_M", "REAL_ESTATE_24_M", "REAL_ESTATE_29_M", 
    "TRAFFIC_01_S", "TRAFFIC_02_S", "TRAFFIC_09_S", "TRAFFIC_15_S", "TRAFFIC_18_M"
]

def clean_law_text(text):
    if not text: return ""
    return text.replace(" ", "").replace("제", "").replace("조", "")

def check_match(expected, law_name, article):
    expected_clean = clean_law_text(expected)
    target_clean = clean_law_text(f"{law_name}{article}")
    return expected_clean in target_clean or target_clean in expected_clean

def run_diagnosis():
    print("🚀 RAG Retrieval Diagnosis (Phase 2.2) Starting...")
    
    # 1. RAG 인스턴스 초기화 (진단용으로 retrieval_k=200 강제 설정)
    pipeline = LegalRAGPipeline()
    pipeline.initialize()
    
    # 임시로 검색 범위 확장
    DIAG_K = 200
    pipeline.bm25_retriever.top_k = DIAG_K
    pipeline.vector_retriever.top_k = DIAG_K
    
    # 2. Golden Dataset 로드
    with open('tests/golden_dataset.json', 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    results = []
    
    for case_id in FAILED_CASES:
        scenario = next((s for s in dataset if s['test_id'] == case_id), None)
        if not scenario:
            print(f"⚠️ {case_id} not found in dataset.")
            continue
            
        print(f"\n🔍 Diagnosing: {case_id}")
        
        # 첫 번째 턴 기준으로 진단 (실패의 시작점)
        turn = scenario['turns'][0]
        query = turn['user_input']
        expected_statute = turn.get('expected_statutes', [""])[0] if turn.get('expected_statutes') else ""
        
        if not expected_statute:
            print(f"  - No expected statute defined for {case_id}")
            continue

        # 검색 수행
        bm25_res = pipeline.bm25_retriever.search(query)
        vector_res = pipeline.vector_retriever.search(query)
        fused_indices = pipeline.rrf_fusion.fuse(bm25_res, vector_res)
        
        # 순위 추적
        def get_rank(results, target_law_article, is_indices=False):
            for rank, item in enumerate(results, 1):
                if is_indices:
                    idx = item
                else:
                    idx = item[0]
                
                meta = pipeline.corpus[idx].get('metadata', {})
                if check_match(target_law_article, meta.get('law_name', ''), meta.get('article', '')):
                    return rank
            return -1

        bm25_rank = get_rank(bm25_res, expected_statute)
        vector_rank = get_rank(vector_res, expected_statute)
        fused_rank = get_rank(fused_indices, expected_statute, is_indices=True)
        
        # Reranking (Top 30 기준)
        reranked_res = pipeline.reranker.rerank(query, pipeline.corpus, fused_indices)
        rerank_rank = get_rank(reranked_res, expected_statute)

        # Corpus 존재 여부 확인 (최후의 보루)
        in_corpus = any(check_match(expected_statute, item.get('metadata', {}).get('law_name', ''), item.get('metadata', {}).get('article', '')) for item in pipeline.corpus)

        results.append({
            "Case ID": case_id,
            "Expected": expected_statute,
            "In Corpus": "✔" if in_corpus else "✘",
            "BM25 Rank": bm25_rank if bm25_rank > 0 else "✘",
            "Vector Rank": vector_rank if vector_rank > 0 else "✘",
            "Fused Rank": fused_rank if fused_rank > 0 else "✘",
            "Final Rank": rerank_rank if rerank_rank > 0 else "✘",
            "Root Cause": "Retrieval Fail" if fused_rank < 0 else ("Rerank Fail" if rerank_rank < 0 else "Scoring Issue")
        })

    # 결과 리포트 출력
    report_df = pd.DataFrame(results)
    print("\n" + "="*80)
    print("📊 RAG Retrieval Diagnosis Result")
    print("="*80)
    print(report_df.to_markdown(index=False))
    print("="*80)
    
    # 파일로 저장
    report_df.to_markdown('tests/results/diagnosis_report_v8_64.md', index=False)
    print(f"\n📝 Report saved to: tests/results/diagnosis_report_v8_64.md")

if __name__ == "__main__":
    run_diagnosis()
