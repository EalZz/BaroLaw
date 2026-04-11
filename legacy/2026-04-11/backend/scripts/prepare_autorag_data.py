import os
import pandas as pd
import psycopg2
from uuid import uuid4

# Database connection URL (Host 환경에서 실행 대비)
DB_URL = os.getenv("KNOWLEDGE_DB_URL", "postgresql://user:password@localhost:5432/knowledge_db")

def main():
    print("1. Knowledge DB에 접속 중...")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"[오류] DB 연결 실패: {e}")
        return

    # 1. Corpus 생성 (교과서 데이터)
    print("2. 법령 및 Q&A 데이터를 교과서(Corpus) 형태로 변환 중...")
    corpus_data = []
    
    # 1-1. 법령 조문 추출
    cur.execute("SELECT id, law_name, article, content FROM statutes")
    statutes = cur.fetchall()
    for s in statutes:
        # AutoRAG가 인식할 고유 문서 ID 발급
        doc_id = f"statute_{s[0]}"
        # 검색 대상이 될 본문 내용 병합
        content = f"{s[1]} {s[2]}\n{s[3]}" 
        corpus_data.append({
            "doc_id": doc_id,
            "contents": content,
            "metadata": {"source": "statute", "law_name": s[1], "article": s[2]}
        })

    # 1-2. 생활법률 QA 추출
    cur.execute("SELECT id, question, answer FROM official_qa")
    official_qas = cur.fetchall()
    for q in official_qas:
        doc_id = f"qa_{q[0]}"
        content = f"질문: {q[1]}\n답변: {q[2]}"
        corpus_data.append({
            "doc_id": doc_id,
            "contents": content,
            "metadata": {"source": "official_qa"}
        })

    corpus_df = pd.DataFrame(corpus_data)
    
    # 2. QA 데이터셋(정답지) 생성
    print("3. Official Q&A를 바탕으로 정답지(QA Dataset) 생성 중...")
    qa_data = []
    for q in official_qas:
        # 질문 단위의 고유 ID
        qa_id = str(uuid4()) 
        # 이 질문에 대해 AutoRAG가 "반드시 찾아내야만 하는" 문서의 ID
        doc_id = f"qa_{q[0]}" 
        
        qa_data.append({
            "qid": qa_id,
            "query": q[1],                  # 사용자의 가상 질문
            "retrieval_gt": [[doc_id]],     # NDCG 평가용 정답 문서 (2차원 배열 지원)
            "generation_gt": [q[2]]         # LLM 생성 평가(RAGAS)용 모범 답안
        })
    
    qa_df = pd.DataFrame(qa_data)

    # 3. 데이터프레임을 파케이(Parquet) 파일로 저장
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "autorag_data")
    os.makedirs(output_dir, exist_ok=True)
    
    corpus_path = os.path.join(output_dir, "corpus.parquet")
    qa_path = os.path.join(output_dir, "qa.parquet")
    
    # pyarrow 또는 fastparquet 엔진 필요
    corpus_df.to_parquet(corpus_path, engine="pyarrow")
    qa_df.to_parquet(qa_path, engine="pyarrow")

    print("====================================")
    print(f"✅ 변환 완료!")
    print(f"- 교과서(Corpus) 문서 수 : {len(corpus_df)}건 -> {corpus_path}")
    print(f"- 정답지(QA) 질문 수    : {len(qa_df)}건 -> {qa_path}")
    print("====================================")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
