import os
import json
import re
import logging
import httpx
from typing import Optional, List
from schemas import LegalIntent, LegalCategory
from prompts import PREPROCESSOR_SYSTEM_PROMPT

logger = logging.getLogger("BaroLaw-Preprocessor")

# Ollama 설정 (app.py 기준)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama-server")
OLLAMA_CHAT_URL = f"http://{OLLAMA_HOST}:11434/api/chat"
# MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma2")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma4:5b")

def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "rag_config.yaml")
    if os.path.exists(config_path):
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

class LegalPreprocessor:
    """[Phase 28.9] Pydantic AI를 완전히 제거하고 네이티브 Ollama API를 직접 호출하는 초경량 전처리기."""
    
    def __init__(self):
        self.config = load_config()
        refinement = self.config.get('refinement', {})
        self.shield_config = refinement.get('domain_shield', {})

    async def analyze(self, query: str, history: Optional[str] = None) -> LegalIntent:
        """
        사용자의 질문을 분석하여 구조화된 LegalIntent 객체를 반환합니다.
        (Ollama API 직접 호출 - 88초 지연 및 400 에러 해결)
        """
        try:
            user_msg = f"사용자 질문: {query}"
            if history:
                user_msg = f"이전 대화 맥락: {history}\n\n현재 사용자 질문: {query}"
            
            # 1. Ollama 네이티브 API 직접 호출 (Pydantic AI 라이브러리 우회)
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": PREPROCESSOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg}
                ],
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.1,  # 결정론적 응답 유도
                    "top_p": 0.1
                }
            }
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(OLLAMA_CHAT_URL, json=payload)
                if response.status_code != 200:
                    raise Exception(f"Ollama API Error: {response.status_code} - {response.text}")
                
                content = response.json().get("message", {}).get("content", "").strip()
                logger.debug(f"--- [Preprocessor Raw Response] ---\n{content}\n--------------------------------")
            
            # 2. 강건한 JSON 추출 루틴
            intent_data = self._extract_json(content, query)
            intent = LegalIntent(**intent_data)

            # 3. v3.9 도메인 실드 및 키워드 정제
            if intent.category == LegalCategory.UNCERTAIN:
                intent.legal_keywords = []
            else:
                intent.legal_keywords = self._purify_keywords(intent.legal_keywords, query, intent.category)
            
            logger.info(f"--- [Preprocessor v3.9] Category: {intent.category} | Keywords: {intent.legal_keywords} ---")
            return intent
            
        except Exception as e:
            logger.error(f"--- [Preprocessor v3.9 Fatal Error] {e} ---")
            return LegalIntent(
                category=LegalCategory.UNCERTAIN,
                legal_keywords=[],
                factual_summary=query,
                is_multiturn_continuation=False,
                missing_info_request="죄송합니다. 서버 분석 도중 오류가 발생했습니다."
            )

    def _extract_json(self, content: str, original_query: str) -> dict:
        """문자열에서 JSON을 안전하게 추출합니다."""
        try:
            # 1. 정규표현식으로 가장 바깥쪽 {} 찾기
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            data = json.loads(content)
            # 필수 필드 보정
            data.setdefault("category", "UNCERTAIN")
            data.setdefault("legal_keywords", [])
            data.setdefault("factual_summary", original_query)
            data.setdefault("is_multiturn_continuation", False)
            data.setdefault("missing_info_request", "")
            return data
        except:
            return {
                "category": "UNCERTAIN",
                "legal_keywords": [],
                "factual_summary": original_query,
                "is_multiturn_continuation": False
            }


    # [v9.0 Phase 1] 중복 정의된 _purify_keywords 메서드 삭제 (Cleanup)
    def _purify_keywords(self, keywords: List[str], original_query: str, category: Optional[LegalCategory] = None) -> List[str]:
        """도메인 실드: 특정 도메인에서 고스트 키워드 강제 제거."""
        import re
        clean_keywords = []
        ghosts = self.shield_config.get('ghost_keywords', [])
        targets = self.shield_config.get('target_domains', [])
        
        for kw in keywords:
            kw = str(kw).strip()
            if not kw: continue
            
            # [v9.0 Phase 2] 도메인 실드 양방향 확장: 특정 도메인에서 고스트 키워드 강제 제거
            if category and str(category.value) in targets:
                if any(ghost in kw for ghost in ghosts):
                    continue
            
            # [v9.0 Phase 2] 역방향 도메인 실드: TRAFFIC/REAL_ESTATE 도메인에서 형법 키워드 필터링
            criminal_targets = self.shield_config.get('criminal_targets', [])
            criminal_ghosts = self.shield_config.get('criminal_ghosts', [])
            if category and str(category.value) in criminal_targets:
                if any(ghost in kw for ghost in criminal_ghosts):
                    continue

            if any(x in kw for x in ["법", "조", "제"]):
                clean_keywords.append(kw); continue
            
            clean_kw = re.sub(r'[^가-힣0-9\s]', '', kw)
            clean_kw = re.sub(r'(죄|하다|상의|의|에)$', '', clean_kw)
            if len(clean_kw) >= 2: clean_keywords.append(clean_kw)
                
        return sorted(list(set(clean_keywords)))[:8]
