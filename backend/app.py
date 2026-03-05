from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
import logging
import json
import pytz
import httpx
import sys
from sqlalchemy import desc
import asyncio

# RAG 및 데이터베이스 모듈 임포트
from rag import search_relevant_context, build_rag_context, get_first_referenced_id, get_model, get_reranker
from database import (
    SessionUser, get_or_create_profile, create_chat_session, 
    save_chat_message, ChatSession, ChatMessage, get_user_sessions, get_session_history
)

# 로깅
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceAI-Server")

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI 설정
MODEL_NAME = "gemma2"
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
    db = SessionUser()
    try:
        sessions = get_user_sessions(db, uid)
        return [{"id": str(s.session_id), "title": s.title if s.title else "새 대화"} for s in sessions]
    finally:
        db.close()

@app.get("/sessions/{session_id}/history")
async def get_history_api(session_id: str):
    db = SessionUser()
    try:
        history = get_session_history(db, session_id)
        return [{"content": m.content, "isUser": (m.role == "user")} for m in history]
    finally:
        db.close()

@app.delete("/sessions/{session_id}")
async def delete_session_api(session_id: str):
    db = SessionUser()
    try:
        from database import delete_chat_session
        success = delete_chat_session(db, session_id)
        return {"success": success}
    finally:
        db.close()

# ------------------------------------------------------------
# [AI 스트리밍 엔진 - 법적 근거 강화]
# ------------------------------------------------------------

def prepare_chat_context(uid: str, user_text: str, session_id: str = None):
    db = SessionUser()
    try:
        profile = get_or_create_profile(db, uid)
        session = None
        
        if session_id and session_id not in ["null", "undefined", ""]:
            session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if not session:
                session = create_chat_session(db, profile.profile_id, first_query=user_text, session_id=session_id)
        
        if not session:
            session = create_chat_session(db, profile.profile_id, first_query=user_text)

        past_msgs = db.query(ChatMessage)\
                      .filter(ChatMessage.session_id == session.session_id)\
                      .order_by(ChatMessage.created_at.desc())\
                      .limit(6).all()
        past_msgs.reverse()

        # RAG 검색 (무거운 연산)
        rag_results = search_relevant_context(user_text)
        rag_context = build_rag_context(rag_results)
        ref_id, ref_type = get_first_referenced_id(rag_results)

        save_chat_message(db, str(session.session_id), role="user", content=user_text)
        
        past_msg_dicts = [{"role": msg.role, "content": msg.content} for msg in past_msgs]
        
        return {
            "session_id": str(session.session_id),
            "past_msgs": past_msg_dicts,
            "rag_results": rag_results,
            "rag_context": rag_context,
            "ref_id": ref_id,
            "ref_type": ref_type,
            "is_new_session": len(past_msgs) == 0
        }
    finally:
        db.close()

async def update_session_title_in_background(session_id: str, text: str):
    import uuid
    # [부하 분산] 메인 LLM이 답변(스트리밍)을 충분히 끝마칠 수 있도록 15초 지연 후 시작
    await asyncio.sleep(15)
    logger.info(f"--- [Title Summary] Task Started for SID: {session_id} ---")
    prompt = f"다음 사용자의 질문을 분석하여 2~3단어의 명사형 제목으로 요약해. 다른 수식어 없이 딱 제목만 말해.\n\n질문: {text}"
    try:
        logger.info(f"--- [Title Summary] Requesting Ollama... ---")
        # [타임아웃 대폭 연장] 긴 답변을 생성하고 있는 중에 큐(Queue)에 대기할 수 있으므로, 120초 여유 부여
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(OLLAMA_CHAT_URL, json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.1}
            })
            if resp.status_code == 200:
                summary = resp.json().get("message", {}).get("content", "").strip()
                logger.info(f"--- [Title Summary] Ollama Response: {summary} ---")
                summary = summary.replace('"', '').replace("'", "").replace("**", "").replace("###", "").strip()
                if summary:
                    def _update():
                        db = SessionUser()
                        try:
                            try:
                                uuid_val = uuid.UUID(session_id)
                            except ValueError:
                                logger.error(f"--- [Title Summary] Invalid UUID format: {session_id} ---")
                                return
                                
                            s = db.query(ChatSession).filter(ChatSession.session_id == uuid_val).first()
                            if s:
                                s.title = summary[:50]
                                db.commit()
                                logger.info(f"--- [Title Summary] Successfully updated DB title to: {s.title} ---")
                            else:
                                logger.error(f"--- [Title Summary] Session not found in DB: {session_id} ---")
                        finally:
                            db.close()
                    await asyncio.to_thread(_update)
            else:
                logger.error(f"--- [Title Summary] Ollama API Error: HTTP {resp.status_code} ---")
    except Exception as e:
        import traceback
        logger.error(f"--- [Title Summary] Fatal Error: {repr(e)} ---")
        logger.error(traceback.format_exc())

async def generate_ai_stream(request: Request, uid: str, user_text: str, current_time: str, session_id: str = None):
    try:
        # [백엔드 병목 해결] 시간이 오래 걸리는 DB 및 RAG 처리를 비동기 스레드 풀에서 실행합니다.
        ctx = await asyncio.to_thread(prepare_chat_context, uid, user_text, session_id)
        real_session_id = ctx["session_id"]
        rag_results = ctx["rag_results"]
        
        if ctx.get("is_new_session"):
            asyncio.create_task(update_session_title_in_background(real_session_id, user_text))
            
        # [핵심] 법적 근거 섹션 및 상세 데이터 구성
        legal_basis_content = ""
        legal_details_content = ""
        
        if rag_results["statutes"]:
            # 1. 화면에 표시될 텍스트 리스트
            legal_basis_content = (
                "\n\n---[LEGAL_BASIS]---\n"
                "⚖️ **법적 근거 및 참고 문헌**\n" + 
                "\n".join([f"- {s['law_name']} {s['article']}" for s in rag_results["statutes"]])
            )
            
            # 2. 클릭 시 보여줄 상세 데이터 (JSON)
            details = [
                {
                    "title": f"{s['law_name']} {s['article']}", 
                    "content": s.get('content', '상세 내용이 없습니다.')
                } for s in rag_results["statutes"]
            ]
            legal_details_content = f"\n---[LEGAL_DETAILS]---\n{json.dumps(details, ensure_ascii=False)}"
        elif rag_results["qa"]:
            legal_basis_content = (
                "\n\n---[LEGAL_BASIS]---\n"
                "📌 **참고 자료**\n- 국가 법령 정보 및 생활법률 상담 가이드라인"
            )

        # 프롬프트 구성 (환각 제어 및 이모지/마크다운 활용)
        system_msg = (
            "너는 서민들의 어려움을 해결해 주는 상냥하고 친절한 법률 상담 AI야. 시작할 때 자기소개는 하지 말고 반드시 '해요체'(~해요, ~하세요)를 사용해."

            "[상담 원칙]"
            "1. 🎯 상황 파악보다 '행동 요령' 선제 제시 (스무고개 금지): 사용자가 피해 사실을 언급하면, 구체적인 정황을 꼬치꼬치 되묻지 마. 정보가 부족하더라도 질문으로만 답변을 끝내지 말고, \"만약 ~한 상황이라면 이렇게 하세요\"처럼 예상되는 상황을 전제로 즉각적인 행동 요령(증거 수집, 신고 방법 등)을 먼저 상세히 안내해."
            "2. 📍 상황 파악 및 객관성 유지: 제공된 [참고 법률 정보]는 사용자의 사연이 아니니, 사용자가 말하지 않은 사연을 지어내어 판단하지 마. 정보가 부족하면 자연스럽게 되묻되, 무관한 정황까지 꼬치꼬치 묻지는 마."
            "3. 🛠️ 단계적이고 현실적인 해결책: 단계적인 해결 방법이 필요하면 1단계, 2단계 등 순차적인 행동 요령(신고 방법, 준비물 등)을 상세히 설명해. 단, 대한민국의 일반적인 상식(예: 블랙박스 확보, 비상등 점등 등)에 기반하여 현실적으로 불가능한 행동(예: 개인이 신호등 조작)은 절대 제안하지 마."
            "4. ✨ 가독성 극대화: 상황별 조치 단계나 소제목에는 반드시 마크다운 헤딩(### )과 적절한 이모지를 사용하여 크고 진하게 보이도록 구분해. 헤딩 기호(###) 앞뒤에 별표(**)를 붙이는 등 마크다운 문법을 절대 섞어 쓰지 마. (올바른 예: ### 🚨 1단계) 부가 설명은 쉽게 풀어 써. (이모지 남발 금지)"
            "5. 🚫 중복 및 전문 용어 노출 금지: 답변 본문 안에는 '법적 근거', '관련 법령', '제O조' 등의 문구를 직접 나열하지 마. 시스템이 답변 끝에 알아서 붙일 거야."

            f"{ctx['rag_context']}\n\n"
            f"[현재 시각]: {current_time}"
        )
        
        messages = [{"role": "system", "content": system_msg}]
        for msg in ctx["past_msgs"]:
            messages.append({"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]})
        messages.append({"role": "user", "content": user_text})

        logger.info(f"--- [AI 요청] SID: {real_session_id} ---")

        full_resp = ""
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", OLLAMA_CHAT_URL, json={
                "model": MODEL_NAME, "messages": messages, "stream": True,
                "options": {"temperature": 0.3}
            }) as response:
                
                async for line in response.aiter_lines():
                    if await request.is_disconnected():
                        break

                    if line:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            
                            if token:
                                full_resp += token
                                sys.stdout.write(token)
                                sys.stdout.flush()
                                yield f"data: {json.dumps({'message': token, 'done': False}, ensure_ascii=False)}\n\n"

                            if chunk.get("done"):
                                # [순서 원복] 답변 종료 후 법률 정보 전송
                                if legal_basis_content:
                                    basis_data = json.dumps({'message': legal_basis_content, 'done': False}, ensure_ascii=False)
                                    yield f"data: {basis_data}\n\n"
                                    
                                    if legal_details_content:
                                        details_data = json.dumps({'message': legal_details_content, 'done': False}, ensure_ascii=False)
                                        yield f"data: {details_data}\n\n"
                                    
                                    full_resp += (legal_basis_content + legal_details_content)

                                def _save_answer():
                                    db = SessionUser()
                                    try:
                                        save_chat_message(db, real_session_id, role="ai", content=full_resp, ref_type=ctx["ref_type"], ref_id=ctx["ref_id"])
                                    finally:
                                        db.close()
                                await asyncio.to_thread(_save_answer)
                                
                                logger.info("\n--- [완성] 답변 저장 완료 ---")
                                yield f"data: {json.dumps({'message': '', 'done': True}, ensure_ascii=False)}\n\n"
                                break
                        except Exception as e:
                            logger.error(f"Error in stream loop: {e}")
                            continue
    except Exception as e:
        logger.error(f"Fatal error in generate_ai_stream: {e}")


@app.get("/chat-stream")
async def chat_stream(request: Request, text: str, uid: str, session_id: str = None):
    return StreamingResponse(
        generate_ai_stream(request, uid, text, datetime.now(pytz.timezone('Asia/Seoul')).isoformat(), session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/metrics")
@app.get("/metrics/")
@app.get("/api/metrics")
async def metrics():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)