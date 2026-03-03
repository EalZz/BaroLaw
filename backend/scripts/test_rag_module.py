from rag import search_relevant_context, build_rag_context, get_first_referenced_id

print("=== RAG 모듈 테스트 ===")
query = "중고거래 사기를 당했어요. 어떻게 신고하죠?"
results = search_relevant_context(query)

print(f"\n법령 검색 결과: {len(results['statutes'])}건")
for s in results["statutes"]:
    print(f"  [{s['law_name']} | {s['article']}] 유사도: {s['similarity']}")
    print(f"  내용: {s['content'][:80]}...")

print(f"\nQ&A 검색 결과: {len(results['qa'])}건")
for q in results["qa"]:
    print(f"  [유사도 {q['similarity']}] Q: {q['question'][:50]}...")

ctx = build_rag_context(results)
print(f"\n--- 생성된 프롬프트 컨텍스트 ---")
print(ctx if ctx else "(없음: 유사도 0.6 미달)")

ref_id, ref_type = get_first_referenced_id(results)
print(f"\n참조 ID: {ref_id} / 타입: {ref_type}")
print("\n=== 테스트 완료 ===")
