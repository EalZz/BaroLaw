"""
rag.py
========
Knowledge DB(pgvector)에서 관련 법령 및 Q&A를 검색하여
LLM 프롬프트에 삽입할 컨텍스트를 생성하는 RAG 모듈.

설계 원칙:
  - 임베딩 모델은 서버 기동 시 1회만 로딩 (싱글톤)
  - 유사도 임계값(0.6) 미달 시 해당 결과를 프롬프트에서 생략
  - statutes Top 2 + official_qa Top 1 = 최대 3건
"""

import os
import logging
import psycopg2
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("RAG")

# ================================================
# 설정값
# ================================================
MODEL_NAME = "jhgan/ko-sroberta-multitask"
SIMILARITY_THRESHOLD = 0.30  # 법령/QA 검색 감도 상향 조정 (0.45 -> 0.3)
STATUTE_TOP_K = 2            # 법령 조문 최대 검색 수
QA_TOP_K = 1                 # Q&A 최대 검색 수
CONTENT_MAX_LEN = 300        # 법령 조문 최대 길이 (토큰 절약)
ANSWER_MAX_LEN = 400         # Q&A 답변 최대 길이

_KNOWLEDGE_DB_URL = os.getenv(
    "KNOWLEDGE_DB_URL",
    "postgresql://user:password@db:5432/knowledge_db"
)

# Docker 외부(WSL/Host) 환경에서 실행 시 'db' → 'localhost' 자동 치환
if not os.getenv("KNOWLEDGE_DB_URL") and not os.path.exists("/.dockerenv"):
    _KNOWLEDGE_DB_URL = _KNOWLEDGE_DB_URL.replace("@db:", "@localhost:")

# ================================================
# 임베딩 모델 싱글톤 (서버 기동 시 최초 1회만 로딩)
# ================================================
_model: SentenceTransformer = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"RAG: 임베딩 모델 로딩 중... ({MODEL_NAME})")
        # GPU(CUDA)가 사용 가능하면 할당 (속도 개선)
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = SentenceTransformer(MODEL_NAME, device=device)
        logger.info(f"RAG: 임베딩 모델 로딩 완료. (Device: {device})")
    return _model


# ================================================
# 핵심 검색 함수
# ================================================
def search_relevant_context(query: str) -> dict:
    """
    사용자 질문을 벡터화하여 knowledge_db에서 관련 법령/Q&A를 검색합니다.

    Returns:
        {
            "statutes": [{"id", "law_name", "article", "content", "similarity"}],
            "qa":       [{"id", "question", "answer", "similarity"}]
        }
    """
    model = get_model()
    query_vector = model.encode(query).tolist()

    results = {"statutes": [], "qa": []}

    try:
        conn = psycopg2.connect(_KNOWLEDGE_DB_URL)
        cur = conn.cursor()

        # 1. 법령 조문 검색 (Top 2, 유사도 ≥ 0.6)
        cur.execute("""
            SELECT id, law_name, article, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM statutes
            WHERE 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (query_vector, query_vector, SIMILARITY_THRESHOLD, query_vector, STATUTE_TOP_K))

        for row in cur.fetchall():
            results["statutes"].append({
                "id": row[0],
                "law_name": row[1],
                "article": row[2],
                "content": row[3][:CONTENT_MAX_LEN],
                "similarity": round(row[4], 3)
            })

        # 2. 생활법률 Q&A 검색 (Top 1, 유사도 ≥ 0.6)
        cur.execute("""
            SELECT id, question, answer,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM official_qa
            WHERE 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (query_vector, query_vector, SIMILARITY_THRESHOLD, query_vector, QA_TOP_K))

        for row in cur.fetchall():
            results["qa"].append({
                "id": row[0],
                "question": row[1],
                "answer": row[2][:ANSWER_MAX_LEN],
                "similarity": round(row[3], 3)
            })

        cur.close()
        conn.close()

        total = len(results["statutes"]) + len(results["qa"])
        logger.info(f"RAG 검색 완료: 법령 {len(results['statutes'])}건, Q&A {len(results['qa'])}건 (총 {total}건)")

    except Exception as e:
        logger.error(f"RAG 검색 오류: {e}")
        # 검색 실패 시 빈 결과 반환 → 일반 응답으로 폴백

    return results


def build_rag_context(rag_results: dict) -> str:
    """
    검색 결과를 LLM 프롬프트에 삽입할 컨텍스트 문자열로 변환합니다.

    Returns:
        - 결과가 없으면 빈 문자열 반환 (프롬프트에 아무것도 추가 안 함)
        - 결과가 있으면 '[참고 법률 정보]' 블록 반환
    """
    if not rag_results["statutes"] and not rag_results["qa"]:
        return ""

    parts = ["[참고 법률 정보] (아래 내용을 근거로 답변하세요. 원문 그대로 인용하지 말고 쉽게 풀어서 설명하세요.)"]

    for s in rag_results["statutes"]:
        parts.append(f"▶ {s['law_name']} {s['article']}\n{s['content']}")

    for q in rag_results["qa"]:
        parts.append(f"▶ 생활법률 안내\nQ: {q['question']}\nA: {q['answer']}")

    return "\n\n".join(parts)


def get_first_referenced_id(rag_results: dict):
    """
    AI 답변 저장 시 사용할 주요 참조 ID 및 타입을 반환합니다.
    우선순위: statutes > qa
    Returns: (id: int|None, type: str|None)
    """
    if rag_results["statutes"]:
        return rag_results["statutes"][0]["id"], "STATUTE"
    if rag_results["qa"]:
        return rag_results["qa"][0]["id"], "OFFICIAL_GUIDE"
    return None, None
