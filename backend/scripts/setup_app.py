import os

# Define the file path
app_py_path = "/home/ksj/voice-chatbot-toy/backend/app.py"

# Define tokens using chr() to avoid tool parsing issues
SS = chr(60) + chr(124) + "system" + chr(124) + chr(62)
SE = chr(60) + chr(124) + "end" + chr(124) + chr(62)
US = chr(60) + chr(124) + "user" + chr(124) + chr(62)
AS = chr(60) + chr(124) + "assistant" + chr(124) + chr(62)

content = f'''from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
import requests, os, logging, time, json, pytz
from urllib.parse import quote
from rag import search_relevant_context, build_rag_context, get_first_referenced_id
from database import SessionUser, get_or_create_profile, create_chat_session, save_chat_message, ChatSession, ChatMessage

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceAI-Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_NAME = "llama3:8b"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_URL = f"http://{{OLLAMA_HOST}}:11434/api/generate"

# Llama 3 Tokens
SS = "{SS}"
SE = "{SE}"
US = "{US}"
AS = "{AS}"

class TextRequest(BaseModel):
    text: str

async def generate_ai_stream(uid: str, user_text: str, current_time: str, client_type: str = "app"):
    db = SessionUser()
    try:
        # 1. Profile management
        profile = get_or_create_profile(db, uid)

        # 2. Session management (get latest or create)
        session = db.query(ChatSession)\\
                    .filter(ChatSession.profile_id == profile.profile_id)\\
                    .order_by(ChatSession.updated_at.desc()).first()
        if not session:
            session = create_chat_session(db, profile.profile_id, first_query=user_text)

        # 3. History (latest 6 messages)
        past_msgs = db.query(ChatMessage)\\
                      .filter(ChatMessage.session_id == session.session_id)\\
                      .order_by(ChatMessage.created_at.asc())\\
                      .limit(6).all()

        # 4. RAG
        rag_results = search_relevant_context(user_text)
        rag_context = build_rag_context(rag_results)
        ref_id, ref_type = get_first_referenced_id(rag_results)

        # 5. Detail mode check
        detail_keywords = ["자세히", "자세하게", "상세히", "구체적으로"]
        is_detail_mode = any(kw in user_text for kw in detail_keywords)
        response_style = (
            "단계별로 나누어 구체적으로 설명하세요. 법적 근거와 실제 대응 방법을 함께 설명하세요."
            if is_detail_mode else
            "핵심만 2~3문장 이내로 해요체로 답변하세요."
        )

        # 6. Prompt Construction
        base_instruction = (
            "너는 서민 생활 밀착형 법률 상담 AI야. "
            "사용자의 실제 상황에 맞게 쉽고 친절하게 답변해. "
            "법률 전문 용어는 쉽게 풀어서 설명하고, 법적 근거를 반드시 포함해."
        )
        system_prompt = base_instruction + "\\n\\n"
        if rag_context:
            system_prompt += rag_context + "\\n\\n"
        system_prompt += (
            f"[현재 상황]\\n"
            f"- 시간: {{current_time}}\\n"
            f"- 응답 방식: {{response_style}}"
        )

        # Prompt assembly
        full_prompt = f"{{SS}}\\n{{system_prompt}}{{SE}}\\n"
        for msg in past_msgs:
            role_tag = US if msg.role == "user" else AS
            full_prompt += f"{{role_tag}}\\n{{msg.content}}{{SE}}\\n"
        
        # Save user message
        save_chat_message(db, session.session_id, role="user", content=user_text)
        
        # Add current query
        full_prompt += f"{{US}}\\n{{user_text}}{{SE}}\\n{{AS}}\\n"

        # 7. Ollama Call
        full_response_text = ""
        response = requests.post(OLLAMA_URL, json={{
            "model": MODEL_NAME, "prompt": full_prompt, "stream": True
        }}, stream=True, timeout=120)

        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                token = chunk.get("response", "")
                full_response_text += token
                yield f"data: {{json.dumps({chr(123)}'token': token, 'done': False{chr(125)})}}\\n\\n"

                if chunk.get("done"):
                    try:
                        save_chat_message(
                            db, session.session_id, role="ai", 
                            content=full_response_text, 
                            referenced_type=ref_type, 
                            referenced_id=ref_id
                        )
                    except Exception as e:
                        logger.error(f"DB Save Error: {{e}}")

                    audio_url = f"/get-audio/{{os.path.basename(generate_tts(full_response_text))}}" if client_type == "web" else None
                    yield f"data: {{json.dumps({chr(123)}'token': '', 'done': True, 'audio_url': audio_url, 'full_text': full_response_text{chr(125)})}}\\n\\n"
                    break
    finally:
        db.close()

def generate_tts(text):
    audio_filename = f"res_{{int(time.time())}}.mp3"
    audio_path = os.path.join("/tmp", audio_filename) if os.path.exists("/tmp") else audio_filename
    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=ko&q={{quote(text[:200])}}"
    try:
        audio_res = requests.get(tts_url)
        with open(audio_path, "wb") as f:
            f.write(audio_res.content)
    except Exception as e:
        logger.error(f"TTS Error: {{e}}")
    return audio_path

@app.get("/")
async def root():
    return {{"message": "Server is running", "ollama_endpoint": OLLAMA_URL}}

@app.get("/ping")
async def ping():
    return {{"status": "alive", "time": datetime.now(pytz.timezone('Asia/Seoul')).isoformat()}}

@app.get("/chat-stream")
async def chat_stream(text: str, uid: str, lat: float = None, lon: float = None, client_type: str = "app"):
    tz_korea = pytz.timezone('Asia/Seoul')
    current_time = datetime.now(tz_korea).strftime("%Y년 %m월 %d일 %H시 %M분")
    return StreamingResponse(
        generate_ai_stream(uid, text, current_time, client_type),
        media_type="text/event-stream"
    )

@app.get("/get-audio/{{filename}}")
async def get_audio(filename: str):
    file_path = os.path.join("/tmp", filename) if os.path.exists("/tmp") else filename
    return FileResponse(file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

with open(app_py_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Successfully written to {app_py_path}")
