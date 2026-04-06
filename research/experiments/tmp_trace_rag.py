import os
import psycopg2
from sentence_transformers import SentenceTransformer, CrossEncoder, util
import torch

MODEL_NAME = "jhgan/ko-sroberta-multitask"
RERANKER_NAME = "Dongjin-kr/ko-reranker"
DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"

def trace(query):
    print(f"QUERY: {query}")
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    reranker = CrossEncoder(RERANKER_NAME, device="cpu")
    
    query_vector = model.encode(query).tolist()
    query_tensor = torch.tensor(query_vector).to("cpu")
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, law_name, article, content
        FROM statutes
        ORDER BY embedding <=> %s::vector
        LIMIT 200;
    """, (query_vector,))
    
    candidates = []
    for row in cur.fetchall():
        candidates.append({
            "type": "statute",
            "id": row[0],
            "law_name": row[1],
            "article": row[2],
            "content": row[3][:1500]
        })
        
    print(f"--- 1st Stage Candidates (Top 10) ---")
    pairs = []
    for i, c in enumerate(candidates):
        text = f"{c['law_name']} {c['article']} {c['content']}"
        pairs.append([query, text])
        print(f"[{i+1}] {c['law_name']} {c['article']}")
        
    rerank_scores = reranker.predict(pairs)
    
    print("\n--- Scoring Details ---")
    for i, c in enumerate(candidates):
        base_score = float(rerank_scores[i])
        title_text = f"{c['law_name']} {c['article']}"
        title_vector = model.encode(title_text, convert_to_tensor=True).to("cpu")
        title_sim = util.cos_sim(query_tensor.unsqueeze(0), title_vector.unsqueeze(0)).item()
        
        final_score = (base_score * 0.7) + (title_sim * 0.3)
        print(f"ID {c['id']} | {title_text[:30]} | Final: {final_score:.4f} | Rerank: {base_score:.4f} | Title: {title_sim:.4f}")

if __name__ == "__main__":
    # Gemma가 정제해준 키워드를 포함한 확장 쿼리로 시뮬레이션
    trace("소매치기를 당했어요 절도죄, 강도죄, 재물절취")
