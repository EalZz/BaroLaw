import requests
from bs4 import BeautifulSoup
import re

def inspect_page(csm_seq):
    url = f"https://www.easylaw.go.kr/CSP/OnhunqueansLstRetrieve.laf?csmSeq={csm_seq}"
    print(f"--- Inspecting csmSeq={csm_seq} ({url}) ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    print(f"Status Code: {r.status_code}")
    
    soup = BeautifulSoup(r.text, 'lxml')
    
    # 모든 링크 추출
    links = soup.select('a')
    print(f"Total links found: {len(links)}")
    
    # Q&A 상세 페이지로 추측되는 링크 패턴 검색
    for a in links:
        text = a.get_text(strip=True)
        onclick = a.get('onclick', '')
        href = a.get('href', '')
        if 'onhun' in onclick.lower() or 'onhun' in href.lower() or 'qna' in text.lower():
            print(f"Link: {text} | onclick: {onclick} | href: {href}")

    # 목록 자체가 본문 하단에 박혀있는지 확인
    titles = soup.select('p.qna_tit_v')
    print(f"Total qna_tit_v found: {len(titles)}")
    for t in titles:
        print(f"Title: {t.get_text(strip=True)}")

if __name__ == "__main__":
    inspect_page('147') # 주택임대차
