import json
import httpx
import asyncio
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

# [Phase 29] Generator Test Infrastructure (Simple & Fast Strategy)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434/api/chat"

class ModelTester:
    def __init__(self, models: Optional[List[str]] = None):
        # 현재 Ollama list에 있는 모델명으로 업데이트
        self.models = models or ["gemma2:latest", "llama3.1:latest", "legal-8b:latest"]
        self.results_dir = "models" # 현재 실행 디렉토리 하위의 models
        os.makedirs(self.results_dir, exist_ok=True)

    async def generate_response(self, model: str, messages: List[Dict[str, str]], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Ollama API를 통해 스트리밍 없이 응답을 수집합니다."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options or {"temperature": 0.3}
        }
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                start_time = datetime.now()
                resp = await client.post(OLLAMA_URL, json=payload)
                end_time = datetime.now()
                
                if resp.status_code == 200:
                    result = resp.json()
                    content = result.get("message", {}).get("content", "")
                    
                    # [Tag Extraction] AI 답변에서 태그 분리 로직
                    body, basis, details = self._segment_response(content)
                    
                    return {
                        "model": model,
                        "body": body,
                        "basis": basis,
                        "details": details,
                        "raw_content": content,
                        "latency": (end_time - start_time).total_seconds(),
                        "done": True
                    }
                else:
                    print(f"Error for {model}: {resp.status_code} - {resp.text}")
                    return {"error": f"HTTP {resp.status_code}", "model": model}
        except Exception as e:
            print(f"Exception for {model}: {str(e)}")
            return {"error": str(e), "model": model}

    def _segment_response(self, full_text: str):
        """본문과 태그(LEGAL_BASIS, LEGAL_DETAILS)를 분리합니다."""
        basis_sep = "---[LEGAL_BASIS]---"
        details_sep = "---[LEGAL_DETAILS]---"
        
        parts_basis = full_text.split(basis_sep)
        body = parts_basis[0].strip()
        
        basis = ""
        details = ""
        
        if len(parts_basis) > 1:
            after_basis = parts_basis[1]
            parts_details = after_basis.split(details_sep)
            basis = parts_details[0].strip()
            if len(parts_details) > 1:
                details = parts_details[1].strip()
        
        return body, basis, details

    async def run_test_suite(self, queries: List[str], system_prompt: str):
        """모든 모델에 대해 테스트 셋을 실행합니다."""
        for query in queries:
            print(f"--- [Testing Query]: {query[:30]}... ---")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            
            tasks = [self.generate_response(model, messages) for model in self.models]
            results = await asyncio.gather(*tasks)
            
            # 결과 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            for res in results:
                if "error" in res: continue
                m_name = res["model"].replace(":", "_")
                m_dir = os.path.join(self.results_dir, m_name)
                os.makedirs(m_dir, exist_ok=True)
                
                with open(os.path.join(m_dir, f"resp_{timestamp}.json"), "w", encoding="utf-8") as f:
                    json.dump(res, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # 실제 기획된 나이브 프롬프트 파일 로드
    prompt_path = "prompts/system_prompts/naive_friendly.txt"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            sample_system = f.read()
    else:
        sample_system = "친절한 AI 변호사 BaroLaw입니다. 해요체로 답하고 태그를 지키세요."
    
    test_queries = [
        "[참고 법령: 형법 제319조(주거침입) 사람의 주거, 관리하는 건조물, 선박이나 항공기 또는 점유하는 방실에 침입한 자는 3년 이하의 징역 또는 500만원 이하의 벌금에 처한다.]\n"
        "질문: 비밀번호를 몰래 알아내서 전 여친 집에 들어갔는데 주거침입죄인가요? 위 법령을 참고해서 상냥하게 답해주세요."
    ]
    tester = ModelTester()
    asyncio.run(tester.run_test_suite(test_queries, sample_system))
