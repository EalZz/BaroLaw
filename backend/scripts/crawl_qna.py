import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import os

def crawl_qna_list(csm_seq):
    """특정 csmSeq의 Q&A 목록을 가져와 상세 페이지 파라미터들을 반환합니다."""
    url = f"https://www.easylaw.go.kr/CSP/OnhunqueansLstPopRetrieve.laf?csmSeq={csm_seq}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        qna_items = []
        # 질문들이 포함된 p 태그와 onclick 이벤트 파싱
        # <p onclick="showSmgSummToggle1('smg_a0','0','90','3142'); return false;">
        questions = soup.select('div.ttl p')
        
        for q in questions:
            text = q.get_text(strip=True)
            onclick = q.get('onclick', '')
            
            # showSmgSummToggle1('smg_a0','0','90','3142') 형태 파싱
            match = re.search(r"showSmgSummToggle1\(.*?,.*?, *'(\d+)', *'(\d+)'\)", onclick)
            if match:
                ast_seq = match.group(1)
                item_seq = match.group(2)
                qna_items.append({
                    'question': text,
                    'onhunqnaAstSeq': ast_seq,
                    'onhunqueSeq': item_seq
                })
        
        return qna_items
    except Exception as e:
        print(f"Error crawling list for {csm_seq}: {e}")
        return []

def crawl_qna_detail(ast_seq, item_seq):
    """AJAX 엔드포인트를 통해 상세 Q&A 내용을 가져옵니다."""
    url = "https://www.easylaw.go.kr/CSP/OnhunqnaRetrieveLstPopAjax.laf"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        'onhunqnaAstSeq': ast_seq,
        'onhunqueSeq': item_seq
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 상세 해설 본문 추출
        # AJAX 응답은 보통 텍스트나 표 형태의 HTML 조각임
        # 모든 텍스트를 정제하여 가져옴
        content = soup.get_text(separator="\n", strip=True)
        
        return {
            'answer_detail': content
        }
    except Exception as e:
        print(f"Error crawling detail for item_seq {item_seq}: {e}")
        return None

def process_topic(topic_name, csm_id_list):
    print(f"--- Processing Topic: {topic_name} ---")
    all_data = []
    for csm_id in csm_id_list:
        print(f"Fetching list for csmSeq={csm_id}...")
        items = crawl_qna_list(csm_id)
        if not items:
            print(f"No items found for csmSeq={csm_id}. Skipping...")
            continue
            
        print(f"Found {len(items)} questions.")
        
        for i, item in enumerate(items):
            print(f"[{topic_name}] Crawling {i+1}/{len(items)}: {item['question'][:30]}...")
            detail = crawl_qna_detail(item['onhunqnaAstSeq'], item['onhunqueSeq'])
            if detail:
                all_data.append({
                    'topic': topic_name,
                    'question': item['question'],
                    'answer': detail['answer_detail'],
                    'source_url': f"https://www.easylaw.go.kr/CSP/OnhunqueansLstPopRetrieve.laf?csmSeq={csm_id}"
                })
            time.sleep(1) # 서버 보호 및 차단 방지
            
    if all_data:
        df = pd.DataFrame(all_data)
        os.makedirs('data/guide', exist_ok=True)
        file_path = f'data/guide/{topic_name}_qa.parquet'
        df.to_parquet(file_path, index=False)
        print(f"Saved {len(all_data)} items to {file_path}")
    else:
        print(f"No data collected for {topic_name}")

if __name__ == "__main__":
    topics = {
        'traffic': ['684', '1506'],
        'estate': ['629', '627', '1972'],
        'fraud': ['272', '1592'],
        'criminal': ['538']
    }
    
    for topic, ids in topics.items():
        process_topic(topic, ids)
