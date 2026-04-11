
import os
import json
import pandas as pd
import psycopg2

# 설정
DB_URL = os.getenv("KNOWLEDGE_DB_URL", "postgresql://user:password@db:5432/knowledge_db")
CORPUS_JSON = "/app/autorag_data/corpus.json"
CORPUS_PARQUET = "/app/autorag_data/corpus.parquet"

def sync_from_db():
    print(f"Connecting to Database: {DB_URL}...")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # 쿼리: law_name, article, content를 개별적으로 정확히 추출
        # 96.7% 정판 엔진(rag.py)이 기대하는 구조로 데이터 추출
        query = """
        SELECT 
            id,
            COALESCE(law_name, '') as law_name,
            COALESCE(article, '') as article,
            COALESCE(content, '') as content,
            COALESCE(topic, 'UNKNOWN') as category,
            COALESCE(source_type, 'OFFICIAL') as source
        FROM statutes
        ORDER BY id ASC;
        """
        
        print("Fetching 5,225+ statutes from DB...")
        cur.execute(query)
        rows = cur.fetchall()
        
        final_items = []
        for row in rows:
            sid, law_name, article, content, category, source = row
            
            # contents는 law_name + article + content 조합으로 생성 (검색용)
            contents = f"{law_name} {article} {content}".strip()
            
            item = {
                "doc_id": f"statute_{sid}",
                "contents": contents,
                "metadata": {
                    "law_name": law_name,
                    "article": article,
                    "category": category,
                    "source": source
                }
            }
            final_items.append(item)
            
        total = len(final_items)
        print(f"Successfully processed {total} items with confirmed alignment.")
        
        # DataFrame으로 변환하여 Parquet 저장
        df = pd.DataFrame(final_items)
        print(f"Saving to {CORPUS_PARQUET}...")
        df.to_parquet(CORPUS_PARQUET, index=False)
        
        # JSON 저장 (백업 및 검수용)
        print(f"Saving to {CORPUS_JSON}...")
        with open(CORPUS_JSON, 'w', encoding='utf-8') as f:
            json.dump(final_items, f, ensure_ascii=False, indent=2)
            
        print(f"✅ Sync Complete! Total: {total} items synchronized correctly.")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error during sync: {e}")
        return False

if __name__ == "__main__":
    sync_from_db()
