# routers.py — 구버전 라우터 파일 (비활성화)
# 현재 모든 API 엔드포인트는 app.py에서 관리됩니다.
# 이 파일은 main.py가 임포트하므로 빈 라우터 객체만 유지합니다.

from fastapi import APIRouter

router = APIRouter()

# 구버전 /chat-stream 라우터는 app.py로 통합되었습니다.
# 새 RAG 파이프라인(rag.py)이 app.py의 generate_ai_stream()에 직접 연결됩니다.
