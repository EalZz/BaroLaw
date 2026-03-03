"""
test_semantic_search.py
========================
사용자의 질문을 벡터화하여 pgvector(knowledge_db)에서 
가장 유사도가 높은 법령 및 Q&A 상위 3개를 검색한다.
"""

import psycopg2
from sentence_transformers import SentenceTransformer
import numpy as np

# 설정
KNOWLEDGE_DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"
MODEL_NAME = "jhgan/ko-sroberta-multitask"

def search_knowledge(query_text):
    print(f"\n[❓ 질문]: {query_text}")
    print("-" * 50)
    
    # 1. 모델 로딩 및 질문 벡터화
    print("AI 모델이 질문의 의미를 분석 중...")
    model = SentenceTransformer(MODEL_NAME)
    query_embedding = model.encode(query_text).tolist()
    
    conn = psycopg2.connect(KNOWLEDGE_DB_URL)
    cur = conn.cursor()
    
    try:
        # 2. pgvector 시맨틱 검색 (코사인 유사도 정렬)
        # <=> 는 코사인 거리를 뜻하며, 작을수록(0에 가까울수록) 유사도가 높음
        
        print("\n--- [법령 조문 검색 결과 (Top 3)] ---")
        cur.execute("""
            SELECT law_name, article, content, 1 - (embedding <=> %s::vector) AS similarity
            FROM statutes
            ORDER BY embedding <=> %s::vector
            LIMIT 3;
        """, (query_embedding, query_embedding))
        
        for r in cur.fetchall():
            print(f"📍 [{r[0]} | {r[1]}] (유사도: {r[3]:.4f})")
            content = r[2].replace('\n', ' ')[:150] + "..."
            print(f"   내용: {content}\n")

        print("\n--- [생활법률 Q&A 검색 결과 (Top 3)] ---")
        cur.execute("""
            SELECT question, answer, 1 - (embedding <=> %s::vector) AS similarity, source_url
            FROM official_qa
            ORDER BY embedding <=> %s::vector
            LIMIT 3;
        """, (query_embedding, query_embedding))
        
        for r in cur.fetchall():
            print(f"📍 [Q: {r[0][:50]}...] (유사도: {r[2]:.4f})")
            answer = r[1].replace('\n', ' ')[:150] + "..."
            print(f"   A: {answer}")
            print(f"   출처: {r[3]}\n")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    # 사용자님의 테스트 질문
    test_query = "중고거래 사기를 당했을 때 어떻게 대응해야 하나요? 신고 방법이나 처벌 규정이 궁금합니다."
    search_knowledge(test_query)
