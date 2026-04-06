
import os
import sys

# 디렉토리 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.rag import search_relevant_context, extract_article_numbers, get_model, get_reranker
import logging

logging.basicConfig(level=logging.INFO)

def debug_fraud_04():
    query = "직원이 포스기에서 고의로 현금 취소하고 돈을 챙긴 걸 CCTV로 확인했습니다."
    category = "FRAUD"
    llm_keywords = ["직원", "포스기", "현금", "취소", "돈", "CCTV"]
    
    print(f"\n--- Debugging FRAUD_04_S ---")
    print(f"Query: {query}")
    print(f"Category: {category}")
    print(f"Keywords: {llm_keywords}")
    
    results = search_relevant_context(
        query=query,
        original_query=query,
        turn_count=1,
        llm_keywords=llm_keywords,
        session_category=category
    )
    
    print("\n--- Final Results (Top 3) ---")
    for s in results["statutes"]:
        print(f"ID: {s['id']}, Law: {s['law_name']}, Article: {s['article']}, Sim: {s['similarity']}")
        print(f"Content: {s['content'][:100]}...")
        print("-" * 20)

if __name__ == "__main__":
    debug_fraud_04()
