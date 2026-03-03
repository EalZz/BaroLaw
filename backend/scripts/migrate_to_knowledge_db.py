"""
migrate_to_knowledge_db.py
===========================
Parquet 원본 데이터(법령 조문 + 생활법률 Q&A)를
PostgreSQL knowledge_db의 statutes / official_qa 테이블에 적재한다.
(임베딩은 별도 Step 3-B에서 처리)
"""

import pandas as pd
import glob
import os
import psycopg2
from psycopg2.extras import execute_values

KNOWLEDGE_DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"


def migrate_statutes(cur):
    """법령 조문 데이터를 statutes 테이블에 적재"""
    print("\n=== [1/2] Statute Migration ===")
    cur.execute("DELETE FROM statutes;")

    files = sorted(glob.glob('data/statute/*.parquet'))
    total = 0

    for f in files:
        df = pd.read_parquet(f)
        topic = df.iloc[0]['topic'] if 'topic' in df.columns else os.path.basename(f).replace('.parquet', '')

        data = []
        for _, row in df.iterrows():
            data.append((
                topic,
                row['법령명'],
                row['조문'],
                row['내용'],
                'STATUTE'
            ))

        execute_values(
            cur,
            "INSERT INTO statutes (topic, law_name, article, content, source_type) VALUES %s",
            data
        )
        total += len(data)
        print(f"  {topic}: {len(data)}건 적재 완료")

    print(f"  => Statute 총 {total}건 적재 완료")
    return total


def migrate_qa(cur):
    """생활법률 Q&A 데이터를 official_qa 테이블에 적재"""
    print("\n=== [2/2] Official Q&A Migration ===")
    cur.execute("DELETE FROM official_qa;")

    files = sorted(glob.glob('data/guide/*_qa.parquet'))
    total = 0

    for f in files:
        df = pd.read_parquet(f)

        data = []
        for _, row in df.iterrows():
            data.append((
                row['topic'],
                row['question'],
                row['answer'],
                row.get('source_url', ''),
                'OFFICIAL_GUIDE'
            ))

        execute_values(
            cur,
            "INSERT INTO official_qa (topic, question, answer, source_url, source_type) VALUES %s",
            data
        )
        topic_name = os.path.basename(f).replace('_qa.parquet', '')
        total += len(data)
        print(f"  {topic_name}: {len(data)}건 적재 완료")

    print(f"  => Official Q&A 총 {total}건 적재 완료")
    return total


def main():
    print("=" * 50)
    print("Knowledge DB Migration Start")
    print("=" * 50)

    conn = psycopg2.connect(KNOWLEDGE_DB_URL)
    cur = conn.cursor()

    try:
        s_count = migrate_statutes(cur)
        q_count = migrate_qa(cur)
        conn.commit()

        print("\n" + "=" * 50)
        print(f"Migration Complete!")
        print(f"  Statutes: {s_count}건")
        print(f"  Q&A:      {q_count}건")
        print(f"  Total:    {s_count + q_count}건")
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
