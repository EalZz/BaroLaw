import pandas as pd
import glob
import os
import psycopg2
from psycopg2.extras import execute_values

KNOWLEDGE_DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"

def migrate_statutes():
    print("--- Starting Statute Migration ---")
    conn = psycopg2.connect(KNOWLEDGE_DB_URL)
    cur = conn.cursor()
    
    # 기존 데이터 삭제 (멱등성 확보)
    cur.execute("DELETE FROM statutes;")
    
    # data/statute/*.parquet 파일 탐색
    files = glob.glob('data/statute/*.parquet')
    
    total_count = 0
    for f in files:
        topic = os.path.basename(f).replace('.parquet', '')
        print(f"Processing topic: {topic}...")
        
        df = pd.read_parquet(f)
        
        # 필드 명칭 매핑 (데이터셋 구조에 따라 조정 가능)
        # 예상 컬럼: '법령명', '조문내용' 등 (이전 단계에서 확인한 구조 기준)
        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((
                topic,
                row.get('법령명', 'Unknown'),
                row.get('조항', ''), # 이전 데이터셋 특성에 맞춤
                row.get('조문내용', row.get('full_text', '')),
                'STATUTE'
            ))
        
        insert_query = """
            INSERT INTO statutes (topic, law_name, article, content, source_type)
            VALUES %s
        """
        execute_values(cur, insert_query, data_to_insert)
        total_count += len(data_to_insert)
        print(f"  Inserted {len(data_to_insert)} rows for {topic}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"--- Finished! Total {total_count} statutes migrated. ---")

if __name__ == "__main__":
    migrate_statutes()
