
import os
import psycopg2
from sentence_transformers import SentenceTransformer

# 설정
MODEL_NAME = "jhgan/ko-sroberta-multitask"
DB_URL = os.getenv("KNOWLEDGE_DB_URL", "postgresql://user:password@db:5432/knowledge_db")

def seed_statutes():
    print(f"Loading embedding model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    statutes_to_add = [
        {
            "law_name": "민법",
            "article": "제565조(해약금)",
            "content": "매매의 당사자 일방이 계약당시에 금전 기타 물건을 계약금, 보증금등의 명목으로 상대방에게 교부한 때에는 당사자간에 다른 약정이 없는 한 당사자의 일방이 이행에 착수할 때까지 교부자는 이를 포기하고 수령자는 그 배액을 상환하여 매매계약을 해제할 수 있다.",
            "topic": "CIVIL",
            "source_type": "statute"
        },
        {
            "law_name": "민법",
            "article": "제750조(불법행위의 내용)",
            "content": "고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는 그 손해를 배상할 책임이 있다.",
            "topic": "CIVIL",
            "source_type": "statute"
        }
    ]
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        for s in statutes_to_add:
            # 백엔드 RAG 로직과 일치시키기 위해 텍스트 조합 (law_name + article + content)
            embedding_text = f"{s['law_name']} {s['article']} {s['content']}"
            embedding = model.encode(embedding_text).tolist()
            
            cur.execute(
                """
                INSERT INTO statutes (law_name, article, content, topic, source_type, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (s['law_name'], s['article'], s['content'], s['topic'], s['source_type'], embedding)
            )
            print(f"Successfully inserted: {s['law_name']} {s['article']}")
            
        conn.commit()
        print("All data committed successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    seed_statutes()
