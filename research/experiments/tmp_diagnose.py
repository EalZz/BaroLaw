
import os
import psycopg2
from sentence_transformers import SentenceTransformer, CrossEncoder
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Diagnose")

# 설정값 (rag.py와 동일하게 설정)
MODEL_NAME = "jhgan/ko-sroberta-multitask"
RERANKER_NAME = "Dongjin-kr/ko-reranker"
KNOWLEDGE_DB_URL = "postgresql://user:password@localhost:5432/knowledge_db"

def diagnose():
    print(f"--- [진단 시작] 쿼리: '소매치기를 당했어요' ---")
    
    # 1. 모델 로드
    print("모델 로딩 중...")
    model = SentenceTransformer(MODEL_NAME)
    reranker = CrossEncoder(RERANKER_NAME)
    
    query = "소매치기를 당했어요"
    query_vector = model.encode(query).tolist()
    
    # 2. DB 검색 (1차 후보군 추출)
    conn = psycopg2.connect(KNOWLEDGE_DB_URL)
    cur = conn.cursor()
    
    print("\n[1차 벡터 검색 결과 (Top 10)]")
    cur.execute("""
        SELECT id, law_name, article, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM statutes
        ORDER BY embedding <=> %s::vector
        LIMIT 10;
    """, (query_vector, query_vector))
    
    candidates = []
    rows = cur.fetchall()
    if not rows:
        print("DB에서 결과가 없습니다. 임베딩 데이터가 정상적으로 저장되었는지 확인이 필요합니다.")
        return

    for r in rows:
        cand = {
            "id": r[0],
            "law_name": r[1],
            "article": r[2],
            "content": r[3],
            "v_score": float(r[4])
        }
        candidates.append(cand)
        print(f"ID: {cand['id']} | {cand['law_name']} {cand['article']} | 유사도: {cand['v_score']:.4f}")

    # 3. 리랭킹 수행
    print("\n[2차 리랭킹 결과]")
    pairs = [[query, f"{c['law_name']} {c['article']} {c['content']}"] for c in candidates]
    scores = reranker.predict(pairs)
    
    for i, c in enumerate(candidates):
        c["r_score"] = float(scores[i])
        
    candidates.sort(key=lambda x: x["r_score"], reverse=True)
    
    for i, c in enumerate(candidates):
        print(f"{i+1}위: {c['law_name']} {c['article']} | 리랭크 점수: {c['r_score']:.4f} (1차 점수: {c['v_score']:.4f})")
        if "준사기" in c['article'] or "절도" in c['article']:
            print(f"   => 내용 요약: {c['content'][:100]}...")

    cur.close()
    conn.close()

if __name__ == "__main__":
    diagnose()
