"""
create_embeddings.py
======================
PostgreSQL knowledge_db에 적재된 statutes와 official_qa 데이터를 읽어
고급 한어 임베딩 모델(ko-sroberta-multitask)로 벡터화한 뒤 업데이트한다.
"""

import os
import time
import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
import numpy as np

# 설정
KNOWLEDGE_DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"
MODEL_NAME = "jhgan/ko-sroberta-multitask"
BATCH_SIZE = 64 # 배치당 처리량

def update_embeddings(cur, table_name, text_column):
    """지정된 테이블의 텍스트 컬럼을 벡터화하여 embedding 컬럼에 업데이트"""
    print(f"\n--- [1/2] Updating Embeddings for: {table_name} ---")
    
    # 1. 임베딩이 비어있는(NULL) 행 또는 모든 행 가져오기
    # 여기서는 초기 적재이므로 모든 데이터를 가져옵니다.
    cur.execute(f"SELECT id, {text_column} FROM {table_name} WHERE embedding IS NULL;")
    rows = cur.fetchall()
    
    if not rows:
        print(f"  No rows found in {table_name} needing embeddings.")
        return 0
    
    print(f"  Found {len(rows)} rows to process.")
    
    # 2. 모델 로딩 (최초 1회)
    print(f"  Loading model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    # 3. 배치 처리
    total_updated = 0
    start_time = time.time()
    
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]
        
        # 임베딩 생성 (768차원)
        # 리스트 형태의 텍스트 64개를 한 번에 인코딩 (GPU 속도 향상 기대)
        embeddings = model.encode(texts)
        
        # 개별 업데이트 (PostgreSQL pgvector 형식에 맞춰 리스트로 변환)
        for idx, emb in zip(ids, embeddings):
            # pgvector는 파이썬 리스트 또는 numpy 배열을 입력을 받음
            cur.execute(
                f"UPDATE {table_name} SET embedding = %s WHERE id = %s",
                (emb.tolist(), idx)
            )
        
        total_updated += len(batch)
        elapsed = time.time() - start_time
        print(f"  Progress: {total_updated}/{len(rows)} ({total_updated / len(rows) * 100:.1f}%) | Elapsed: {elapsed:.1f}s")

    print(f"  => {table_name} {total_updated}건 임베딩 완료")
    return total_updated

def main():
    print("=" * 50)
    print("Embedding Pipeline Start")
    print("=" * 50)

    conn = psycopg2.connect(KNOWLEDGE_DB_URL)
    cur = conn.cursor()

    try:
        # 1. statutes 테이블 (조문 본문 'content' 기반)
        s_count = update_embeddings(cur, "statutes", "content")
        
        # 2. official_qa 테이블 (질문 'question' 기반으로 우선 생성)
        # 검색 시에는 주로 질문의 유사성을 보기 위함이나, 필요시 질문+답변을 섞을 수 있습니다.
        q_count = update_embeddings(cur, "official_qa", "question")
        
        conn.commit()

        print("\n" + "=" * 50)
        print(f"Embedding Generation Complete!")
        print(f"  Statutes: {s_count}건")
        print(f"  Q&A:      {q_count}건")
        print("=" * 50)

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
