
# 임계값 없이 실제 유사도 상위 3개를 확인하는 진단 스크립트
import psycopg2
from sentence_transformers import SentenceTransformer

KNOWLEDGE_DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"
MODEL_NAME = "jhgan/ko-sroberta-multitask"

print("모델 로딩 중...")
model = SentenceTransformer(MODEL_NAME)
query = "중고거래 사기를 당했어요. 어떻게 신고하죠?"
vec = model.encode(query).tolist()

conn = psycopg2.connect(KNOWLEDGE_DB_URL)
cur = conn.cursor()

print("\n--- statutes Top 3 (임계값 없음) ---")
cur.execute("""
    SELECT law_name, article,
           1 - (embedding <=> %s::vector) AS similarity
    FROM statutes
    ORDER BY embedding <=> %s::vector
    LIMIT 3;
""", (vec, vec))
for r in cur.fetchall():
    print(f"  [{r[0]} | {r[1]}] 유사도: {r[2]:.4f}")

print("\n--- official_qa Top 3 (임계값 없음) ---")
cur.execute("""
    SELECT question,
           1 - (embedding <=> %s::vector) AS similarity
    FROM official_qa
    ORDER BY embedding <=> %s::vector
    LIMIT 3;
""", (vec, vec))
for r in cur.fetchall():
    print(f"  [유사도 {r[1]:.4f}] Q: {r[0][:60]}")

cur.close()
conn.close()
