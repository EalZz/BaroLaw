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
from sentence_transformers import SentenceTransformer, CrossEncoder

logger = logging.getLogger("RAG")

# ================================================
# 설정값
# ================================================
MODEL_NAME = "jhgan/ko-sroberta-multitask"
RERANKER_NAME = "Dongjin-kr/ko-reranker"
FETCH_K = 10                 # 1차 저인망 검색 후보 수 (법령 10건, QA 10건)
FINAL_TOP_K = 3              # 최종 선발 컨텍스트 수
MIN_RERANK_SCORE = 0.0       # 거짓 정보(환각) 차단을 위한 최소 리랭크 점수
CONTENT_MAX_LEN = 1500        # 법령 조문 최대 길이 (토큰 절약)
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

_reranker: CrossEncoder = None

def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        logger.info(f"RAG: 리랭커 모델 로딩 중... ({RERANKER_NAME})")
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _reranker = CrossEncoder(RERANKER_NAME, max_length=512, device=device)
        logger.info(f"RAG: 리랭커 모델 로딩 완료. (Device: {device})")
    return _reranker


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

        candidates = []

        # 1. 1차 저인망 검색 (법령 Top 10)
        cur.execute("""
            SELECT id, law_name, article, content
            FROM statutes
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (query_vector, FETCH_K))

        for row in cur.fetchall():
            candidates.append({
                "type": "statute",
                "id": row[0],
                "law_name": row[1],
                "article": row[2],
                "content": row[3][:CONTENT_MAX_LEN]
            })

        # 2. 1차 저인망 검색 (Q&A Top 10)
        cur.execute("""
            SELECT id, question, answer
            FROM official_qa
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (query_vector, FETCH_K))

        for row in cur.fetchall():
            candidates.append({
                "type": "qa",
                "id": row[0],
                "question": row[1],
                "answer": row[2][:ANSWER_MAX_LEN]
            })

        cur.close()
        conn.close()

        if not candidates:
            return results

        # 3. 리랭킹 수행 (Ko-Reranker)
        reranker = get_reranker()
        pairs = []
        for c in candidates:
            if c["type"] == "statute":
                text = f"{c['law_name']} {c['article']} {c['content']}"
            else:
                text = f"Q: {c['question']} A: {c['answer']}"
            pairs.append([query, text])
            
        scores = reranker.predict(pairs)
        
        for i, c in enumerate(candidates):
            c["score"] = float(scores[i])
            
        # 4. 법적 근거 보장형 통합 선발 (Top-3)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        final_selection = []
        
        # 조건 1: 가장 점수가 높은 법령 1개 무조건 선발
        best_statute = next((c for c in candidates if c["type"] == "statute"), None)
        if best_statute:
            final_selection.append(best_statute)
            candidates.remove(best_statute)
            
        # 조건 2: 남은 후보 중 최고 득점자 2개 추가 (단, 점수가 0을 초과할 때만)
        for c in candidates:
            if len(final_selection) >= FINAL_TOP_K:
                break
            if c["score"] > MIN_RERANK_SCORE:
                final_selection.append(c)

        # 5. 최종 결과를 기존 형식으로 분배
        logger.info("=== RAG 리랭킹 최종 선발 결과 (Top 3) ===")
        for i, c in enumerate(final_selection):
            title = f"{c['law_name']} {c['article']}" if c['type'] == 'statute' else f"Q: {c['question']}"
            logger.info(f"[{i+1}위] 점수: {c['score']:.4f} | 타입: {c['type'].upper():<7} | 제목: {title[:40]}...")

        for c in final_selection:
            if c["type"] == "statute":
                results["statutes"].append({
                    "id": c["id"],
                    "law_name": c["law_name"],
                    "article": c["article"],
                    "content": c["content"],
                    "similarity": round(c["score"], 3)
                })
            else:
                results["qa"].append({
                    "id": c["id"],
                    "question": c["question"],
                    "answer": c["answer"],
                    "similarity": round(c["score"], 3)
                })

        total = len(results["statutes"]) + len(results["qa"])
        logger.info(f"RAG 검색 완료: 1차(20건) -> 리랭킹 -> 최종 {total}건 발탁 (법령 {len(results['statutes'])}, QA {len(results['qa'])})")

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
