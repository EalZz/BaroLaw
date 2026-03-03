import requests
from bs4 import BeautifulSoup

def find_topic_ids():
    # 모든 생활법령 목록이 나오는 페이지
    url = "https://www.easylaw.go.kr/CSP/CsmSortRetrieveLst.laf?sortType=cate"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'lxml')
    
    found = []
    links = soup.select('a')
    for a in links:
        text = a.get_text(separator=' ', strip=True) # 공백 포함 추출
        href = a.get('href', '')
        if 'csmSeq=' in href:
            keywords = ["주택임대차", "상가건물", "보이스피싱", "교통사고", "폭행", "명예훼손", "사기"]
            if any(k in text for k in keywords):
                found.append(f"{text} -> {href}")
    
    # 중복 제거 및 출력
    for item in sorted(list(set(found))):
        print(item)

if __name__ == "__main__":
    find_topic_ids()
