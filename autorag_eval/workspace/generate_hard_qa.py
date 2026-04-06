import pandas as pd
import requests
import os
import json
from tqdm import tqdm

# ---------------------------------------------------------
# 설정 및 경로 (격리된 환경 유지)
# ---------------------------------------------------------
BASE_DIR = os.path.expanduser("~/BaroLaw/autorag_eval/autorag_data")
QA_PATH = os.path.join(BASE_DIR, "qa.parquet")
OUTPUT_PATH = os.path.join(BASE_DIR, "qa_hard.parquet")
LOG_PATH = os.path.expanduser("~/BaroLaw/autorag_eval/workspace/query_verification_log.txt")

# 전송 주소 (현재 시스템에 떠 있는 Ollama 활용)
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma2"

def generate_hard_query(original_query):
    # 실제 사람이 고민 상담하듯이 모호하게 질문을 바꾸는 프롬프트
    prompt = f"""다음 법률 질문을 실제 사람이 법률 상담 게시판에 올릴 법한 아주 자연스러운 구어체 문장으로 1문장만 바꿔주세요.
규칙:
1. '무엇인가요?', '설명해주세요' 같은 기계적인 표현을 쓰지 마세요.
2. 상황 설명(에피소드) 위주로 질문하세요.
3. 핵심 법률 전문 용어를 직접 언급하지 마세요 (예: '음주운전 처벌' -> '술 먹고 운전하다 걸렸는데 어떻게 되나요').
4. 답변은 오직 변환된 '한 문장'만 출력하세요.

원본 질문: '{original_query}'
변환 결과:"""
    
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 100, "temperature": 0.7}
        }, timeout=20)
        
        if response.status_code == 200:
            return response.json().get('response', original_query).strip()
        return original_query
    except Exception as e:
        print(f"Error during Ollama call: {e}")
        return original_query

def main():
    print(f"📦 기존 질문 셋 로딩 중: {QA_PATH}")
    df = pd.read_parquet(QA_PATH)
    
    # 전체 데이터셋에서 100개를 샘플링하여 변환합니다.
    sample_df = df.iloc[:100].copy()
    
    new_queries = []
    log_entries = []
    
    print(f"🤖 Ollama({MODEL_NAME})를 이용해 질문을 '사람답게' 변조 중... (100건)")
    
    for idx, row in tqdm(sample_df.iterrows(), total=len(sample_df)):
        old_q = row['query']
        new_q = generate_hard_query(old_q)
        
        # 따옴표 제거 및 클리닝
        new_q = new_q.replace('"', '').replace("'", "")
        
        new_queries.append(new_q)
        log_entries.append(f"[{idx+1}] 원본: {old_q}\n    변환: {new_q}\n")
    
    sample_df['query'] = new_queries
    
    # 결과 저장
    sample_df.to_parquet(OUTPUT_PATH, index=False)
    
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("=== [BaroLaw] 사람 같은 질문 변조 검증 로그 ===\n\n")
        f.write("\n".join(log_entries))
    
    print(f"\n✅ 가혹한 테스트 셋(qa_hard.parquet) 생성 완료.")
    print(f"📄 검증용 로그 저장됨: {LOG_PATH}")

if __name__ == "__main__":
    main()
