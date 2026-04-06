import json
import os
CORPUS_PATH = os.path.join(os.path.dirname(__file__), "autorag_data", "corpus.json")
LAW_CATEGORY_MAP = {
    "민법": "real_estate",
    "주택임대차보호법": "real_estate",
    "상가건물 임대차보호법": "real_estate",
    "집합건물의 소유 및 관리에 관한 법률": "real_estate",
    "공동주택관리법": "real_estate",
    "형법": "criminal",
    "스토킹범죄의 처벌 등에 관한 법률": "criminal",
    "성폭력범죄의 처벌 등에 관한 특례법": "criminal",
    "아동·청소년의 성보호에 관한 법률": "criminal",
    "동물보호법": "criminal",
    "통신비밀보호법": "criminal",
    "도로교통법": "traffic",
    "특정범죄 가중처벌 등에 관한 법률": "traffic",
    "교통사고처리 특례법": "traffic",
    "자동차손해배상 보장법": "traffic",
    "특정경제범죄 가중처벌 등에 관한 법률": "fraud",
    "전자금융거래법": "fraud",
    "정보통신망 이용촉진 및 정보보호 등에 관한 법률": "digital",
    "개인정보 보호법": "digital",
    "근로기준법": "labor",
}
ARTICLE_OVERRIDE = {
    ("형법", "제314조"): "criminal",
    ("형법", "제260조"): "criminal",
    ("도로교통법", "제12조"): "traffic",
    ("도로교통법", "제27조"): "traffic",
}
def get_category(law_name, article):
    if (law_name, article) in ARTICLE_OVERRIDE:
        return ARTICLE_OVERRIDE[(law_name, article)]
    return LAW_CATEGORY_MAP.get(law_name, "etc")
NEW_STATUTES = [
    {"doc_id": "statute_5215", "contents": "[동물보호법] 제8조(동물학대의 금지) 누구든지 동물을 학대하여서는 아니 된다.", "metadata": {"article": "제8조", "law_name": "동물보호법", "category": "criminal", "source": "statutes", "topic": "동물학대"}},
    {"doc_id": "statute_5216", "contents": "[민법] 제623조(임대인의 의무) 임대인은 목적물을 사용·수익에 필요한 상태로 유지하여야 한다.", "metadata": {"article": "제623조", "law_name": "민법", "category": "real_estate", "source": "statutes", "topic": "누수/수선의무"}},
    {"doc_id": "statute_5217", "contents": "[민법] 제640조(차임연체와 해지) 차임을 연체한 경우 임대인은 계약을 해지할 수 있다.", "metadata": {"article": "제640조", "law_name": "민법", "category": "real_estate", "source": "statutes", "topic": "월세 미납"}},
    {"doc_id": "statute_5218", "contents": "[형법] 제314조(업무방해) 위력으로 사람의 업무를 방해한 자는 처벌한다.", "metadata": {"article": "제314조", "law_name": "형법", "category": "criminal", "source": "statutes", "topic": "업무방해"}},
    {"doc_id": "statute_5219", "contents": "[도로교통법] 제46조의3(난폭운전 금지) 급제동, 급가속 등 위협적인 운전을 하여서는 아니 된다.", "metadata": {"article": "제46조의3", "law_name": "도로교통법", "category": "traffic", "source": "statutes", "topic": "보복운전"}},
    {"doc_id": "statute_5220", "contents": "[도로교통법] 제54조(사고 발생 시 조치) 교통사고를 낸 경우 즉시 정차하여 필요한 조치를 하여야 한다.", "metadata": {"article": "제54조", "law_name": "도로교통법", "category": "traffic", "source": "statutes", "topic": "사고 후 조치"}},
]
def main():
    with open(CORPUS_PATH, 'r', encoding='utf-8') as f:
        corpus = json.load(f)
    print(f"Loaded {len(corpus)} items")
    
    for item in corpus:
        if item.get('doc_id', '').startswith('statute_'):
            law_name = item.get('metadata', {}).get('law_name', '')
            article = item.get('metadata', {}).get('article', '')
            if law_name:
                item['metadata']['category'] = get_category(law_name, article)
    
    corpus.extend(NEW_STATUTES)
    with open(CORPUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
    print(f"Done! Total: {len(corpus)} items")
if __name__ == "__main__":
    main()
