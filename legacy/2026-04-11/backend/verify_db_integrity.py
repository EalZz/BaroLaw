
import os
import psycopg2

# 설정
DB_URL = os.getenv("KNOWLEDGE_DB_URL", "postgresql://user:password@localhost:5432/knowledge_db")

def check_integrity():
    print(f"Connecting to Database for Integrity Check...")
    try:
        # DB 연결 (포트 5432가 호스트에 매핑되어 있다고 가정)
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # 1. 통신비밀보호법 샘플 확인
        print("\n[Test 1] Searching for '통신비밀보호법'...")
        cur.execute("SELECT id, law_name, article, LEFT(content, 100) FROM statutes WHERE law_name LIKE '%통신비밀보호법%' LIMIT 1;")
        res = cur.fetchone()
        if res:
            print(f" - ID: {res[0]}")
            print(f" - Law Name: {res[1]}")
            print(f" - Article: {res[2]}")
            print(f" - Content Preview: {res[3]}...")
        else:
            print(" - Results not found.")

        # 2. 형법 샘플 확인
        print("\n[Test 2] Searching for '형법' Art 347 (사기)...")
        cur.execute("SELECT id, law_name, article, LEFT(content, 100) FROM statutes WHERE law_name = '형법' AND article LIKE '제347조%' LIMIT 1;")
        res = cur.fetchone()
        if res:
            print(f" - ID: {res[0]}")
            print(f" - Law Name: {res[1]}")
            print(f" - Article: {res[2]}")
            print(f" - Content Preview: {res[3]}...")
        else:
            print(" - Results not found.")

        conn.close()
    except Exception as e:
        print(f"❌ Error during check: {e}")

if __name__ == "__main__":
    check_integrity()
