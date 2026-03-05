import httpx
import json

MODEL_8B = "legal-8b:latest"
MODEL_3B = "legal-3b:latest"

async def call_ollama_stream(prompt: str, model_type: str = "8b"):
    target_model = MODEL_8B if model_type == "8b" else MODEL_3B
    url = "http://ollama-server:11434/api/generate"
    #url = "http://172.17.0.1:11434/api/generate"
    
    payload = {
        "model": target_model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "stop": [
                "<|eot_id|>",
                "<|end_of_text|>",
                "(참고",
                "(법률",
                "참고:",
                "일반적인 질문에는"
            ]
        }
    }

    print(f"--- [STEP 1] Ollama 연결 시도 시작: {target_model} ---", flush=True)

    # 타임아웃 무제한
    timeout_settings = httpx.Timeout(None)

    try:
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            # stream=True로 데이터 한 줄씩 즉시 받기
            async with client.stream("POST", url, json=payload) as response:
                print(f"--- [STEP 2] Ollama 응답 헤더 수신 (Status: {response.status_code}) ---", flush=True)
                
                if response.status_code != 200:
                    yield "Ollama 서버 응답 에러입니다."
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        
                        if any(bad_word in token for bad_word in ["(참고)", "법률 정보는", "사용자는"]):
                            continue

                        if token:
                            # 특수 태그 필터링
                            if "<|" in token: continue
                            
                            # 서버 로그에 실시간 출력 (매우 중요: 이거 안 찍히면 전송 안 되는 중)
                            print(token, end="", flush=True)
                            yield token
                        
                        if data.get("done"):
                            print(f"\n--- [STEP 3] 생성 완료 ---", flush=True)
                            break
                            
                    except json.JSONDecodeError:
                        continue

    except Exception as e:
        error_msg = f"통신 장애: {type(e).__name__}"
        print(f"\n[!] 에러 발생: {error_msg} -> {str(e)}", flush=True)
        yield error_msg
