import sys
import os
import logging
import asyncio
from datetime import datetime

# backend 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag import search_relevant_context
from app import extract_legal_keywords

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BENCHMARK")

TEST_QUERIES = [
    "소매치기를 당해어요",
    "밤에 모르는 사람이 집에 담을 넘어서 들어왔어요",
    "전화로 검사라고 하면서 돈을 보내라고 해요",
    "술자리에서 시비가 붙어서 맞았어요",
    "길에서 지갑을 주워서 가져갔어요",
    "중고거래 입금을 했는데 물건을 안 보내고 잠수 탔어요",
    "월급이 두 달째 안 들어오고 사장님이 전화를 안 받아요",
    "주차된 차를 누가 긁고 도망갔어요",
    "아랫집에서 밤마다 소리를 지르고 벽을 쳐요",
    "사람을 치고 그냥 가버린 차를 목격했어요"
]

async def run_benchmark():
    report = []
    report.append("# 📊 RAG 성능 벤치마킹 테스트 결과 (10개 시나리오)")
    report.append(f"수행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("\n## 1. 테스트 개요")
    report.append("- **목적**: Z-Score 보정 및 키워드 가중치(+0.5) 도입 후, 각 시나리오별 점수 분포 확인")
    report.append("- **대상**: 대한민국 일상 법률 시나리오 대표 10종")
    report.append("- **핵심 지표**: 최종 점수(Final Score) - 임계값(Threshold) 설정의 근거 자료로 활용")
    report.append("\n---")

    for i, user_query in enumerate(TEST_QUERIES):
        print(f"[{i+1}/10] 테스트 중: {user_query}")
        
        # 1. 키워드 추출 (Gemma 호출)
        legal_keywords = extract_legal_keywords(user_query)
        enriched_query = f"{user_query} {legal_keywords}" if legal_keywords else user_query
        
        # 2. RAG 검색
        context = search_relevant_context(enriched_query)
        
        report.append(f"\n### CASE {i+1}. {user_query}")
        report.append(f"> **확장 키워드**: `{legal_keywords if legal_keywords else '없음'}`")
        
        results = []
        if context["statutes"]:
            for s in context["statutes"]:
                results.append({"type": "법령", "title": f"{s['law_name']} {s['article']}", "score": s["similarity"]})
        if context["qa"]:
            for q in context["qa"]:
                results.append({"type": "QA", "title": f"Q: {q['question'][:30]}...", "score": q["similarity"]})
        
        if not results:
            report.append("- ❌ **검색 결과 없음** (모든 후보가 임계치 미만 탈탈)")
            continue
            
        report.append("| 순위 | 타입 | 제목 | 최종 점수 | 판단(O/X/?) |")
        report.append("| :--- | :--- | :--- | :--- | :--- |")
        
        for idx, res in enumerate(results):
            report.append(f"| {idx+1} | {res['type']} | {res['title']} | **{res['score']:.4f}** | [ ] |")
            
        report.append("\n" + "-" * 60)

    # 결과 파일 저장 (backend 폴더 내)
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_test_results.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print(f"\n✅ 벤치마킹 완료! 결과 리포트 생성됨: {output_path}")

if __name__ == "__main__":
    # Ollama 서버 및 모델 로딩 시간을 고려하여 실행
    asyncio.run(run_benchmark())
