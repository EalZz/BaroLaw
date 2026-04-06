import pandas as pd
import os
import sys
from sqlalchemy import create_engine, text

# 경로 설정
BASE_DIR = '/home/ksj/BaroLaw'
OUTPUT_DIR = os.path.join(BASE_DIR, 'autorag_eval', 'autorag_data')
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'corpus.parquet')

# 기본 KNOWLEDGE_DB_URL (WSL 내 Docker 기준)
KNOWLEDGE_DB_URL = os.getenv("KNOWLEDGE_DB_URL", "postgresql://user:password@localhost:5432/knowledge_db")

def generate_corpus():
    print(f"Connecting to database at {KNOWLEDGE_DB_URL}...")
    try:
        engine = create_engine(KNOWLEDGE_DB_URL)
        corpus_list = []
        
        with engine.connect() as connection:
            # 1. 법령 조문 추출
            print("Fetching statutes...")
            query_s = text("SELECT id, law_name, article, content, topic FROM statutes")
            result_s = connection.execute(query_s)
            count_s = 0
            for row in result_s:
                doc_id = str(row[0])
                contents = f"{row[1]} {row[2]}\n{row[3]}"
                metadata = {"type": "statute", "topic": row[4], "law_name": row[1], "article": row[2]}
                corpus_list.append({
                    'doc_id': doc_id, 'contents': contents.strip(), 'metadata': metadata
                })
                count_s += 1
            print(f"Fetched {count_s} statutes.")

            # 2. Q&A 데이터 추출
            print("Fetching official_qa...")
            query_q = text("SELECT id, question, answer, topic FROM official_qa")
            result_q = connection.execute(query_q)
            count_q = 0
            for row in result_q:
                doc_id = f"qa_{row[0]}"
                contents = f"질문: {row[1]}\n답변: {row[2]}"
                metadata = {"type": "qa", "topic": row[3]}
                corpus_list.append({
                    'doc_id': doc_id, 'contents': contents.strip(), 'metadata': metadata
                })
                count_q += 1
            print(f"Fetched {count_q} QAs.")

        # 3. Parquet 저장
        if corpus_list:
            print(f"Building DataFrame with {len(corpus_list)} items...")
            df = pd.DataFrame(corpus_list)
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            df.to_parquet(OUTPUT_PATH, index=False, engine='pyarrow')
            print(f"Successfully generated corpus at {OUTPUT_PATH}")
        else:
            print("[ALERT] No data found to build corpus.")

    except Exception as e:
        print(f"[ERROR] Failed to generate corpus: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    generate_corpus()
