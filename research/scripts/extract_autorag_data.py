import os
import psycopg2
import pandas as pd

# 환경 변수 또는 로컬 DB (WSL 테스트용 localhost 포트포워딩 활용)
DB_URL = os.getenv("KNOWLEDGE_DB_URL", "postgresql://user:password@localhost:5432/knowledge_db")

def extract_corpus_and_qa():
    print("--- [AutoRAG Data Extraction] Started ---")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return

    # 1. Corpus 데이터 추출 (Statutes + QA Answer)
    # AutoRAG Corpus 형식: doc_id(str), contents(str), metadata(dict)
    
    corpus_data = []
    
    # 1-1. 법령(Statutes) 추출
    print("📌 법령(Statutes) 데이터 추출 중...")
    cur.execute("SELECT id, law_name, article, content FROM statutes;")
    statutes = cur.fetchall()
    for row in statutes:
        doc_id = f"statute_{row[0]}"
        law_name = row[1]
        article = row[2]
        content = row[3]
        
        corpus_data.append({
            "doc_id": doc_id,
            "contents": f"[{law_name}] {article}\n{content}",
            "metadata": {"source": "statutes", "law_name": law_name, "article": article}
        })
    print(f"✅ 법령 {len(statutes)}건 추출 완료.")

    # 1-2. 생활법률 Q&A 답변(QA Answer) 추출을 Corpus로 편입
    # AutoRAG는 QA 데이터셋의 정답(GT)을 Corpus 문서의 doc_id에 매핑해야 합니다.
    print("📌 생활법률(QA) 데이터 추출 중...")
    cur.execute("SELECT id, topic, question, answer FROM official_qa;")
    official_qas = cur.fetchall()
    
    qa_dataset = []
    for row in official_qas:
        qa_id = row[0]
        topic = row[1]
        question = row[2]
        answer = row[3]
        
        doc_id = f"qa_{qa_id}"
        
        # QA 답변을 독립적인 지식 문서(Corpus)로 저장
        corpus_data.append({
            "doc_id": doc_id,
            "contents": f"[{topic}]\nQ: {question}\nA: {answer}",
            "metadata": {"source": "official_qa", "topic": topic}
        })
        
        # 2. QA 데이터셋(Test Set) 구성
        # 질문(Query)과 정답 출처(Retrieval Ground Truth)를 묶어줍니다.
        qa_dataset.append({
            "qid": f"query_{qa_id}",
            "query": question,
            "retrieval_gt": [[doc_id]],  # list of list of str 형식 준수
            "generation_gt": [answer]    # 답변 평가를 위해 정답 답변 추가 (리스트 형식)
        })
    print(f"✅ QA {len(official_qas)}건 추출 완료.")

    cur.close()
    conn.close()

    # 3. Parquet 및 JSONL 파일로 저장
    os.makedirs("autorag_data", exist_ok=True)
    
    corpus_df = pd.DataFrame(corpus_data)
    qa_df = pd.DataFrame(qa_dataset)
    
    # AutoRAG 표준 확장자인 parquet으로 우선 저장
    corpus_df.to_parquet("autorag_data/corpus.parquet", index=False)
    qa_df.to_parquet("autorag_data/qa.parquet", index=False)
    
    print("\n🎉 추출 성공! 파일이 저장되었습니다:")
    print(" - backend/scripts/autorag_data/corpus.parquet")
    print(" - backend/scripts/autorag_data/qa.parquet")

if __name__ == "__main__":
    extract_corpus_and_qa()
