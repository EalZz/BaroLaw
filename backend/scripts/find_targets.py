import requests
from bs4 import BeautifulSoup
import time

def find_all_target_ids():
    # 우리가 필요한 카테고리 목록
    categories = {
        '부동산': 3,
        '금융/금전': 4,
        '민형사': 10,
        '교통': 11,
        '범죄': 17
    }
    
    found_topics = []
    
    for cat_name, ast_seq in categories.items():
        url = f"https://www.easylaw.go.kr/CSP/CsmSortRetrieveLst.laf?sortType=cate&csmAstSeq={ast_seq}"
        print(f"Checking category: {cat_name}...")
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'lxml')
        
        links = soup.select('a')
        for a in links:
            href = a.get('href', '')
            if 'csmSeq=' in href:
                text = a.get_text(strip=True)
                # 불필요한 공백 및 개음 제거
                text = " ".join(text.split())
                if text and len(text) > 1:
                    found_topics.append(f"[{cat_name}] {text} | {href}")
        time.sleep(0.5)

    with open('target_topics.txt', 'w', encoding='utf-8') as f:
        for t in sorted(list(set(found_topics))):
            f.write(t + "\n")
    print(f"Saved {len(found_topics)} topics to target_topics.txt")

if __name__ == "__main__":
    find_all_target_ids()
