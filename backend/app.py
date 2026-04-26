from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, List, Optional
import os
import logging
import json
import pytz
import httpx
import sys
import re
import time
from sqlalchemy import desc
import asyncio

# RAG 및 데이터베이스 모듈 임포트
from rag import search_relevant_context, build_rag_context, get_first_referenced_id, get_model, get_reranker
from database import (
    SessionUser, get_or_create_profile, create_chat_session, 
    save_chat_message, ChatSession, ChatMessage, get_user_sessions, get_session_history
)
from schemas import LegalCategory, LegalIntent
from preprocessor import LegalPreprocessor
from prompts import MAIN_ENGINE_SYSTEM_PROMPT, TITLE_GEN_PROMPT
from legal_synonyms import get_synonyms, guess_category

# 로깅
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("VoiceAI-Server")

app = FastAPI()
# 전처리기 인스턴스
preprocessor = LegalPreprocessor()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI 설정 (v6 MVP Optimized)
MODEL_NAME = "gemma4:5b"
# MODEL_NAME = "gemma2:latest"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama-server")
OLLAMA_CHAT_URL = f"http://{OLLAMA_HOST}:11434/api/chat"

@app.on_event("startup")
async def startup_event():
    logger.info("--- [STARTUP] 가동 준비 완료 ---")
    from database import Base, user_engine
    Base.metadata.create_all(bind=user_engine)
    get_model()    # 임베딩 모델 사전 적재
    get_reranker() # Ko-Reranker 모델 사전 적재

# ------------------------------------------------------------
# [세션 및 히스토리 API]
# ------------------------------------------------------------

@app.get("/sessions/{uid}")
async def list_user_sessions_api(uid: str):
    db_session = SessionUser()
    try:
        sessions = get_user_sessions(db_session, uid)
        return [{"id": str(s.session_id), "title": s.title if s.title else "새 대화"} for s in sessions]
    finally:
        db_session.close()

@app.get("/sessions/{session_id}/history")
async def get_history_api(session_id: str):
    db_session = SessionUser()
    try:
        history = get_session_history(db_session, session_id)
        return [{"content": m.content, "isUser": (m.role == "user")} for m in history]
    finally:
        db_session.close()

@app.delete("/sessions/{session_id}")
async def delete_session_api(session_id: str):
    db_session = SessionUser()
    try:
        from database import delete_chat_session
        success = delete_chat_session(db_session, session_id)
        return {"success": success}
    finally:
        db_session.close()

# ------------------------------------------------------------
# [AI 응답 도우미]
# ------------------------------------------------------------

def build_sse_payload(content: str = "", done: bool = False, is_replacement: bool = False):
    """프론트엔드 통신 규약을 유지하며 SSE 페이로드를 생성합니다."""
    payload_dict = {'message': content, 'done': done, 'is_replacement': is_replacement}
    return f"data: {json.dumps(payload_dict, ensure_ascii=False)}\n\n"

# ------------------------------------------------------------
# [AI 스트리밍 엔진]
# ------------------------------------------------------------

async def prepare_chat_context(uid: str, user_text: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    db_session = SessionUser()
    try:
        profile = get_or_create_profile(db_session, uid)
        chat_session = None
        sid_uuid = None
        if session_id and session_id not in ["null", "undefined", ""]:
            import uuid
            try:
                sid_uuid = uuid.UUID(session_id)
                chat_session = db_session.query(ChatSession).filter(ChatSession.session_id == sid_uuid).first()
            except ValueError:
                pass
        
        if not chat_session:
            # Phase 37: Session ID Injection Fix (T2 연결 보존)
            chat_session = create_chat_session(db_session, profile.profile_id, first_query=user_text, session_id=str(sid_uuid) if sid_uuid else None)

        # 1. 히스토리 로드 (최근 6턴)
        past_msgs_objs = db_session.query(ChatMessage)\
                      .filter(ChatMessage.session_id == chat_session.session_id)\
                      .order_by(ChatMessage.created_at.desc())\
                      .limit(6).all()
        past_msgs_objs.reverse()

        # 2. Pydantic AI 기반 의도 분석
        history_summary = getattr(chat_session, "past_request", "")
        intent: LegalIntent = await preprocessor.analyze(user_text, history=history_summary)
        
        # [Phase 42.3] Aggressive Context Inheritance (Fallback Suppression)
        # 이전 대화 기록이 있고, 현재 질문이 모호하거나(UNCERTAIN) 짧은 경우 기동
        if getattr(chat_session, "current_category", None) and chat_session.current_category != "UNCERTAIN":
            is_weak_intent = (intent.category == LegalCategory.UNCERTAIN or len(user_text.strip()) < 15)
            
            if is_weak_intent:
                try:
                    old_category = intent.category
                    # 기존 카테고리 강제 상속
                    intent.category = LegalCategory(chat_session.current_category)
                    
                    # 팩트 요약 보강: 이전 맥락 + 현재 질문
                    if chat_session.past_request:
                        intent.factual_summary = f"{chat_session.past_request} {user_text}"
                    else:
                        intent.factual_summary = user_text
                        
                    # 중대한 변경: UNCERTAIN일 때만 뜨던 폴백 메시지를 상속 성공 시 제거하여 RAG 강제 수행
                    intent.missing_info_request = "" 
                    logger.info(f"--- [Context Reinforcement] Inherited: {old_category} -> {intent.category} | Summary: {intent.factual_summary} ---")
                except Exception as e:
                    logger.error(f"Context reinforcement failed: {e}")
        
        # 3. [L2] Fallback Suppression (v3.8) - 레거시 브릿지 삭제 완료
        # 신규 전처리기가 자신감 있게 분류하도록 조준경을 맡깁니다.
        
        if intent.category == LegalCategory.UNCERTAIN and intent.missing_info_request:
            is_uncertain = True
            save_chat_message(db_session, str(chat_session.session_id), role="user", content=user_text)
            return {
                "session_id": str(chat_session.session_id),
                "past_msgs": [{"role": m.role, "content": m.content} for m in past_msgs_objs],
                "rag_results": {"statutes": [], "qa": []},
                "rag_context": f"[시스템 안내]\n질문이 다소 모호하여 정확한 법률 안내가 어렵습니다.\n{intent.missing_info_request}",
                "ref_id": None, "ref_type": None,
                "is_new_session": len(past_msgs_objs) == 0,
                "is_uncertain": True
            }
        
        # 4. 세션 상태 업데이트 및 쿼리 융합 (Phase 5.2.3: Query Fusion)
        from database import update_session_state
        
        # M-Turn이고 이전 요약이 있다면 현재 요약 앞에 강제 결합 (맥락 단절 방지)
        if len(past_msgs_objs) > 0 and history_summary:
            fused_summary = f"[{history_summary}] {intent.factual_summary}"
            logger.info(f"--- [v5.2.3 Query Fusion] {intent.factual_summary} -> {fused_summary} ---")
            intent.factual_summary = fused_summary

        update_session_state(db_session, chat_session.session_id, category=intent.category.value, past_request=intent.factual_summary)
        
        # 5. RAG 검색
        past_statutes_raw = getattr(chat_session, "past_statutes", "")
        prev_statutes_list = [s.strip() for s in past_statutes_raw.split(",")] if past_statutes_raw else []
        
        # 3. RAG 기반 관련 법령 검색 (v6.6 지연 시간 측정 추가)
        rag_start = time.time()
        rag_results_dict = await asyncio.to_thread(
            search_relevant_context,
            query=user_text,
            original_query=user_text,
            turn_count=len(past_msgs_objs) // 2 + 1,
            llm_keywords=intent.legal_keywords,
            session_category=intent.category.value if intent.category else "UNCERTAIN"
        )
        rag_duration = time.time() - rag_start
        logger.info(f"--- [Performance] RAG Search took {rag_duration:.2f}s ---")
        
        # 6. 인용 데이터 후처리 (Hint 추출)
        
        # 6. 인용 데이터 후처리 (Hint 추출)
        current_statutes_names = []
        for s_item in rag_results_dict.get("statutes", []):
            raw_n = str(s_item.get('law_name') or "").split(" 제")[0].split("(")[0].strip()
            if len(raw_n) >= 2: current_statutes_names.append(raw_n)
            
        if current_statutes_names:
            # Phase 32/38: 이전 법령 히스토리 업데이트 (최근 10개 유지)
            unique_statutes = list(set(prev_statutes_list + current_statutes_names))
            new_past_str = ",".join(unique_statutes[:10])
            update_session_state(db_session, chat_session.session_id, past_statutes=new_past_str)

        save_chat_message(db_session, str(chat_session.session_id), role="user", content=user_text)
        
        found_ref_id, found_ref_type = get_first_referenced_id(rag_results_dict)

        return {
            "session_id": str(chat_session.session_id),
            "past_msgs": [{"role": m.role, "content": m.content} for m in past_msgs_objs],
            "rag_results": rag_results_dict,
            "rag_context": build_rag_context(rag_results_dict),
            "ref_id": found_ref_id,
            "ref_type": found_ref_type,
            "is_new_session": len(past_msgs_objs) == 0,
            "category": intent.category.value if intent.category else "UNCERTAIN",
            "keywords": intent.legal_keywords,
            "summary": intent.factual_summary,
            "rag_duration": rag_duration # v6.6
        }
    finally:
        db_session.close()

async def update_session_title_in_background(session_id: str, text: str):
    await asyncio.sleep(15)
    prompt_text = TITLE_GEN_PROMPT.format(text=text)
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(OLLAMA_CHAT_URL, json={
                "model": "gemma4:5b", "messages": [{"role": "user", "content": prompt_text}], "stream": False, "think": False
            })
            if resp.status_code == 200:
                summary_text = resp.json().get("message", {}).get("content", "").strip()
                summary_text = re.sub(r'["\'*#]', '', summary_text).strip()
                if summary_text:
                    def _update_db():
                        db_conn = SessionUser()
                        import uuid
                        try:
                            s_obj = db_conn.query(ChatSession).filter(ChatSession.session_id == uuid.UUID(session_id)).first()
                            if s_obj: s_obj.title = summary_text[:50]; db_conn.commit()
                        finally: db_conn.close()
                    await asyncio.to_thread(_update_db)
    except Exception as e:
        logger.error(f"[Title Update Error] {e}")

async def generate_ai_stream(request: Request, uid: str, user_text: str, current_time: str, session_id: Optional[str] = None):
    start_time = time.time()
    sid_for_log = session_id or "unknown"
    try:
        # [Step 1] 컨텍스트 준비
        context_data = await prepare_chat_context(uid, user_text, session_id)
        sid_str = context_data["session_id"]
        sid_for_log = sid_str
        
        # Task 5-4: RAG 준비 완료 로그
        logger.info(f"--- [RAG Ready] Category: {context_data.get('category')}, Keywords: {len(context_data.get('keywords', []))}, RAG Duration: {context_data.get('rag_duration', 0):.2f}s ---")

        if await request.is_disconnected():
            logger.info(f"--- [Stream Cancelled] Client disconnected after RAG: {sid_str} ---")
            return

        if context_data.get("is_uncertain"):
            yield build_sse_payload(context_data["rag_context"], done=True)
            return

        if context_data.get("is_new_session"):
            asyncio.create_task(update_session_title_in_background(sid_str, user_text))

        # [Step 2] 앱 UI용 법적 근거 및 테스트용 메타데이터 준비
        rag_results = context_data["rag_results"]
        legal_basis_content = ""
        legal_details_content = ""
        rag_engine_raw_str = ""
        
        if rag_results.get("statutes"):
            # 1. 앱용 태그 조집 (UI 리스트) - Legacy Format
            legal_basis_content = (
                "\n\n---[LEGAL_BASIS]---\n"
                "⚖️ **법적 근거 및 참고 문헌**\n" + 
                "\n".join([f"- {s['law_name']} {s['article']}" for s in rag_results["statutes"]])
            )
            
            # 2. 앱용 태그 조립 (상세 팝업 JSON) - Legacy Format
            details = [
                {
                    "title": f"{s['law_name']} {s['article']}", 
                    "content": s.get('content', '상세 내용이 없습니다.')
                } for s in rag_results["statutes"]
            ]
            legal_details_content = f"\n---[LEGAL_DETAILS]---\n{json.dumps(details, ensure_ascii=False)}"
            
            # 3. 테스트 엔진용 태그 조립
            raw_statutes = [f"{s['law_name']} {s['article']}" for s in rag_results["statutes"]]
            rag_engine_raw_str = f"\n---[RAG_ENGINE_RESULT]---\n" + "|".join(raw_statutes)
        elif rag_results.get("qa"):
            legal_basis_content = (
                "\n\n---[LEGAL_BASIS]---\n"
                "📌 **참고 자료**\n- 국가 법령 정보 및 생활법률 상담 가이드라인"
            )

        # [Step 3] LLM 스트리밍
        system_msg_full = MAIN_ENGINE_SYSTEM_PROMPT + f"{context_data['rag_context']}\n\n[현재 시각]: {current_time}"
        chat_history_msgs = [{"role": "system", "content": system_msg_full}]
        for m_hist in context_data["past_msgs"]:
            chat_history_msgs.append({"role": "user" if m_hist["role"] == "user" else "assistant", "content": m_hist["content"]})
        chat_history_msgs.append({"role": "user", "content": user_text})

        # Task 5-4: Ollama 스트리밍 시작 로그
        logger.info(f"--- [LLM Start] Entering Ollama streaming stage for session: {sid_str} ---")

        accumulated_resp = ""
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", OLLAMA_CHAT_URL, json={
                "model": MODEL_NAME, "messages": chat_history_msgs, "stream": True, "think": False, "options": {"temperature": 0.3}
            }) as response:
                async for line_raw in response.aiter_lines():
                    if await request.is_disconnected(): 
                        logger.info(f"--- [Stream Cancelled] Client disconnected: {sid_str} ---")
                        break
                    if not line_raw: continue
                    try:
                        chunk_json = json.loads(line_raw)
                        token_str = chunk_json.get("message", {}).get("content", "")
                        if token_str:
                            accumulated_resp += token_str
                            yield build_sse_payload(token_str)
                        
                        if chunk_json.get("done"):
                            # [Step 4] 후처리 및 태그 전송
                            await asyncio.sleep(0.05)
                            
                            if accumulated_resp.startswith("Thinking"):
                                accumulated_resp = re.sub(r'^Thinking\.{0,3}\s*', '', accumulated_resp) or "상담 결과를 생성했습니다."
                                yield build_sse_payload(accumulated_resp, is_replacement=True)
                            
                            # [UI 복구] 안드로이드 앱 인식용 태그 전송
                            if legal_basis_content: yield build_sse_payload(legal_basis_content)
                            if legal_details_content: yield build_sse_payload(legal_details_content)
                            
                            # [테스트 평가] 테스트 엔진용 태그 전송 (앱에서는 무시됨)
                            if rag_engine_raw_str: yield build_sse_payload(rag_engine_raw_str)
                            
                            # [v6.6] 성능 요약 로그 및 메타데이터 전송 (Performance Maintenance)
                            full_duration = time.time() - start_time
                            perf_meta = {
                                "category": context_data.get("category", "UNCERTAIN"),
                                "keywords": context_data.get("keywords", []),
                                "summary": context_data.get("summary", ""),
                                "rag_s": round(context_data.get("rag_duration", 0), 2),
                                "total_s": round(full_duration, 2)
                            }
                            yield build_sse_payload(f"\n---[RAG_METADATA]---\n{json.dumps(perf_meta, ensure_ascii=False)}")
                            logger.info(f"--- [Performance Final] Total: {full_duration:.2f}s (RAG: {context_data.get('rag_duration', 0):.2f}s) ---")

                            yield build_sse_payload("", done=True)
                            
                            def _save_to_db():
                                db_final = SessionUser()
                                try:
                                    # [v2.5 Fix] 'statute_313'와 같은 문자열 ID에서 숫자만 추출하여 DB Integer 타입 불일치 해결
                                    import re
                                    clean_ref_id = None
                                    if context_data.get("ref_id"):
                                        numeric_match = re.search(r'\d+', str(context_data["ref_id"]))
                                        if numeric_match:
                                            clean_ref_id = int(numeric_match.group())
                                            
                                    save_chat_message(
                                        db_final, sid_str, role="ai", 
                                        content=f"{accumulated_resp}{legal_basis_content}{legal_details_content}", 
                                        ref_type=context_data["ref_type"], 
                                        ref_id=clean_ref_id
                                    )
                                finally:
                                    db_final.close()
                            await asyncio.to_thread(_save_to_db)
                            full_duration = time.time() - start_time
                            logger.info(f"--- [Stream Completed] Session: {sid_str}, Total: {full_duration:.2f}s, DB Saved ---")
                            break
                    except json.JSONDecodeError:
                        continue

    except asyncio.CancelledError:
        logger.info(f"--- [Stream Cancelled] Streaming task cancelled: {sid_for_log} ---")
        return
    except Exception as e:
        logger.error(f"[Stream Error] {e}")

@app.get("/chat-stream")
async def chat_stream(request: Request, text: str, uid: str, session_id: Optional[str] = None):
    # Task 5-4: 요청 시작 로그
    logger.info(f"--- [Stream Start] Session: {session_id}, UID: {uid[:8]}..., Text length: {len(text)} ---")
    return StreamingResponse(
        generate_ai_stream(request, uid, text, datetime.now(pytz.timezone('Asia/Seoul')).isoformat(), session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return msg.find("/metrics") == -1 and msg.find("/health") == -1

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
