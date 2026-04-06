import sys
import os
import pandas as pd

# 로컬 임포트를 위한 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'backend'))

from backend.rag import LegalRAGPipeline

def debug_retrieval():
    print("Initializing LegalRAGPipeline...")
    pipeline = LegalRAGPipeline()
    pipeline.initialize()
    
    test_queries = [
        "가게에서 손님이 술 마시고 행패 부리며 집기를 다 부쉈어요.", # CRIMINAL_06_S
        "재물손괴 형법 제366조",
        "형법 제366조",
        "오토바이를 누가 훔쳐갔습니다", # CRIMINAL_10_S
        "형법 제329조"
    ]
    
    def get_info(idx):
        doc = pipeline.corpus[idx]
        meta = doc.get('metadata', {})
        law = meta.get('law_name', 'N/A')
        art = meta.get('article', 'N/A')
        cont = doc.get('contents', 'N/A')[:50].replace('\n', ' ')
        return f"[{law} {art}] {cont}..."

    for q in test_queries:
        print(f"\n" + "="*80)
        print(f"🔍 TESTING QUERY: {q}")
        print("="*80)
        
        # 1. BM25 Search
        bm25_res = pipeline.bm25_retriever.search(q)
        print(f"📡 [BM25] Top 3 Scores:")
        for idx, score in bm25_res[:3]:
            print(f"   - {get_info(idx)} (Score: {score:.2f})")

        # 2. Vector Search
        vector_res = pipeline.vector_retriever.search(q)
        print(f"\n📡 [Vector] Top 3 Scores:")
        for idx, score in vector_res[:3]:
            print(f"   - {get_info(idx)} (Score: {score:.2f})")
            
        # 3. Final Result (with Category Boost)
        print(f"\n📡 [Final] (Including Rerank & Category Boost)")
        final = pipeline.search(q, category="CRIMINAL")
        statutes = final.get("statutes", [])
        print(f"🏆 Final Statutes Count: {len(statutes)}")
        for s in statutes[:5]:
            # statutes items are dicts with 'law_name', 'article', 'content'
            print(f"   - ✅ Found: {s.get('law_name')} {s.get('article')} (Final Score: {s.get('_final_score', 0):.2f})")
            
    print("\n" + "="*80)
    print("Debug completed.")

if __name__ == "__main__":
    debug_retrieval()
