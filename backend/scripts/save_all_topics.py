import requests
from bs4 import BeautifulSoup

def save_all():
    url = "https://www.easylaw.go.kr/CSP/CsmSortRetrieveLst.laf?sortType=cate"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'lxml')
    
    with open('all_topics.txt', 'w', encoding='utf-8') as f:
        links = soup.select('a')
        for a in links:
            href = a.get('href', '')
            if 'csmSeq=' in href:
                text = a.get_text(strip=True)
                f.write(f"{text}|{href}\n")

if __name__ == "__main__":
    save_all()
