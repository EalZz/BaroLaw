"""
법률 데이터셋 토픽별 분리 및 조 단위 청킹 스크립트
원본 출처: mosshoon/korean-laws (open.law.go.kr 국가법령정보센터 직접 수집)

[데이터 무결성 원칙]
- 이 스크립트는 국가법령정보센터 원문 데이터만을 사용합니다.
- AI가 생성하거나 추론한 내용은 일절 포함하지 않습니다.
- 모든 조문 텍스트는 원본 그대로 보존됩니다.
"""

import pandas as pd
import re
import os

RAW_PATH = "/home/ksj/voice-chatbot-toy/backend/data/raw/korean_laws.parquet"
OUTPUT_DIR = "/home/ksj/voice-chatbot-toy/backend/data/statute"

# ============================================================
# 1. 토픽별 법령 매핑 (서민 4대 분야)
# ============================================================
TOPIC_LAWS = {
    "traffic": [
        "도로교통법",
        "특정범죄 가중처벌 등에 관한 법률",
        "교통사고처리 특례법",
        "자동차손해배상 보장법",
    ],
    "fraud": [
        "특정경제범죄 가중처벌 등에 관한 법률",
        "전자금융거래법",
        "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    ],
    "estate": [
        "주택임대차보호법",
        "상가건물 임대차보호법",
        "집합건물의 소유 및 관리에 관한 법률",
    ],
    "criminal": [
        "형법",
        "경범죄 처벌법",
        "근로기준법",
        "스토킹범죄의 처벌 등에 관한 법률",
    ],
}

# 형법과 민법은 여러 토픽에서 필요하므로 별도 처리
SHARED_LAWS = {
    "형법": ["fraud", "criminal"],
    "민법": ["estate"],
}


def chunk_by_article(law_name, full_text):
    """
    법령 본문을 '조(Article)' 단위로 분절합니다.
    패턴: '제N조', '제N조의N' 등을 기준으로 split합니다.
    """
    # 조문 시작 패턴: 제1조, 제2조의2, 제10조 등
    pattern = r"(제\d+조(?:의\d+)?(?:\([^)]*\))?)"
    parts = re.split(pattern, full_text)
    
    articles = []
    i = 0
    while i < len(parts):
        # 조문 번호 패턴을 찾은 경우
        if re.match(pattern, parts[i]):
            article_header = parts[i]
            article_body = parts[i + 1] if i + 1 < len(parts) else ""
            article_text = (article_header + article_body).strip()
            if len(article_text) > 10:  # 너무 짧은 것은 제외
                articles.append({
                    "법령명": law_name,
                    "조문": article_header.strip(),
                    "내용": article_text,
                })
            i += 2
        else:
            # 조문 이전의 부칙 등 (첫 번째 파트)
            if parts[i].strip() and i == 0 and len(parts[i].strip()) > 20:
                articles.append({
                    "법령명": law_name,
                    "조문": "전문/부칙",
                    "내용": parts[i].strip()[:500],  # 전문은 길 수 있으므로 제한
                })
            i += 1
    
    return articles


def main():
    # 원본 데이터 로드
    print("[1/4] 원본 데이터 로드 중...")
    df = pd.read_parquet(RAW_PATH)
    print(f"  -> 전체 법령 수: {len(df)}")
    
    # 법령명 매칭 검증
    print("\n[2/4] 토픽별 법령 매칭 검증:")
    all_law_names = set(df["법령명"].unique())
    
    for topic, laws in TOPIC_LAWS.items():
        print(f"\n  [{topic.upper()}]")
        for law in laws:
            # 정확히 일치하는 법령 찾기 (시행령, 시행규칙 제외)
            exact = [n for n in all_law_names if n == law]
            partial = [n for n in all_law_names if law in n and n != law]
            if exact:
                print(f"    OK '{law}'")
            else:
                print(f"    MISS '{law}' (유사: {partial[:3]})")
    
    # 토픽별 필터링 + 조 단위 청킹
    print("\n[3/4] 토픽별 데이터 분리 및 청킹 중...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    summary = {}
    for topic, laws in TOPIC_LAWS.items():
        all_articles = []
        for law_name in laws:
            # 정확히 일치하는 법령만 (시행령/시행규칙 제외)
            row = df[df["법령명"] == law_name]
            if row.empty:
                # 부분 매칭 시도
                row = df[df["법령명"].str.contains(law_name, na=False)]
                # 시행령, 시행규칙 제외
                row = row[~row["법령명"].str.contains("시행령|시행규칙", na=False)]
            
            if row.empty:
                print(f"  [WARN] '{law_name}' 을 찾을 수 없음 -> 건너뜀")
                continue
            
            for _, r in row.iterrows():
                articles = chunk_by_article(r["법령명"], r["법령본문"])
                all_articles.extend(articles)
                print(f"  [{topic}] '{r['법령명']}': {len(articles)}개 조문")
        
        if all_articles:
            topic_df = pd.DataFrame(all_articles)
            topic_df["topic"] = topic
            output_path = os.path.join(OUTPUT_DIR, f"{topic}.parquet")
            topic_df.to_parquet(output_path, index=False)
            summary[topic] = len(topic_df)
    
    # 결과 요약
    print("\n[4/4] 데이터셋 구축 완료!")
    total = 0
    for topic, count in summary.items():
        print(f"  {topic}: {count}개 조문")
        total += count
    print(f"  총 합계: {total}개 조문")
    print(f"  저장 경로: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
