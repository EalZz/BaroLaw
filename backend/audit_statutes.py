import os
from sqlalchemy import create_engine, text

# Get connection URL
KNOWLEDGE_DB_URL = "postgresql://barolaw_user:barolaw_pass@localhost:5432/barolaw_knowledge"

try:
    engine = create_engine(KNOWLEDGE_DB_URL)

    with engine.connect() as conn:
        print("--- Searching for anomalies in '교통사고처리특례법' ---")
        query = text("SELECT id, law_name, article, LEFT(content, 100) FROM statutes WHERE law_name LIKE '%교통사고처리%' AND article LIKE '%39%'")
        result = conn.execute(query)
        rows = result.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Law: {row[1]} | Article: {row[2]}")
            
        print("\n--- Searching for '제39조' in content of '교통사고처리특례법' ---")
        query = text("SELECT id, law_name, article, LEFT(content, 100) FROM statutes WHERE law_name LIKE '%교통사고처리%' AND content LIKE '%제39조%'")
        result = conn.execute(query)
        rows = result.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Law: {row[1]} | Article: {row[2]}")
            print(f"Content snippet: {row[3]}...")
            
        print("\n--- Check: Common mismatch (Article 39) ---")
        query = text("SELECT id, law_name, article FROM statutes WHERE article LIKE '%39%'")
        result = conn.execute(query)
        for row in result.fetchall():
            print(f"ID: {row[0]} | Law: {row[1]} | Article: {row[2]}")
             
except Exception as e:
    print(f"Error: {e}")
