import os
from sqlalchemy import create_engine, text
import re

KNOWLEDGE_DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"

def audit_and_fix():
    try:
        engine = create_engine(KNOWLEDGE_DB_URL)
        with engine.connect() as conn:
            print("--- [AGGRESSIVE CLEANING] Fixing Law/Article Mismatches ---")
            
            # 1. 법령명은 도로교통법인데 내용/조문에 형법 용어가 포함된 경우 전수 수정
            criminal_keywords = ['상해', '폭행', '협박', '사기', '손괴', '절도', '횡령', '배임', '간간', '추행']
            for kw in criminal_keywords:
                query = text("""
                    UPDATE statutes 
                    SET law_name = '형법' 
                    WHERE law_name = '도로교통법' 
                    AND (content LIKE :kw OR article LIKE :kw)
                """).bindparams(kw=f'%{kw}%')
                res = conn.execute(query)
                if res.rowcount > 0:
                    print(f"Fixed {res.rowcount} entries related to '{kw}' (Road Traffic Act -> Criminal Law)")

            # 2. 존재할 수 없는 조문 번호 (> 166) 일괄 감사 및 보정
            # 조문 번호가 너무 크면 '교통사고처리 특례법'일 확률이 높음 (내용 확인 후 자동 처리 로직은 신중히)
            # 여기서는 명백한 오염 데이터(300번대 이상)를 식별
            cleanup_query = text("""
                UPDATE statutes 
                SET law_name = '형법' 
                WHERE law_name = '도로교통법' 
                AND article ~ '제[2-9][0-9][0-9]조'
            """)
            res_cleanup = conn.execute(cleanup_query)
            print(f"Cleaned up {res_cleanup.rowcount} impossible Road Traffic Act article numbers.")

            conn.commit()
            print("\n--- Aggressive cleaning finished ---")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit_and_fix()
