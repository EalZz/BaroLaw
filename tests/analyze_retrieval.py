
import sys
import os
import psycopg2
import logging

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Analyzer")

# Add backend to path
sys.path.append('/home/ksj/BaroLaw/backend')

# Constants and imports from rag.py
try:
    from rag import get_model, CONTENT_MAX_LEN
    from legal_synonyms import get_synonyms
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# DB URL (manual override for simplicity if needed, but let's try auto)
_KNOWLEDGE_DB_URL = os.getenv(
    "KNOWLEDGE_DB_URL",
    "postgresql://user:password@localhost:5432/knowledge_db"
)

def analyze_case(test_id, query, original_query, expected_statute_pattern):
    print(f"\n{'='*60}")
    print(f" ANALYSIS FOR: {test_id}")
    print(f" Query: {query}")
    print(f" Expected Statute Pattern: {expected_statute_pattern}")
    print(f"{'='*60}")

    model = get_model()
    query_vector = model.encode(query).tolist()

    try:
        conn = psycopg2.connect(_KNOWLEDGE_DB_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return

    # 1. 1st-stage Vector Search (Top 50 to be safe for analysis)
    cur.execute("""
        SELECT id, law_name, article, content, (embedding <=> %s::vector) AS distance
        FROM statutes
        ORDER BY distance
        LIMIT 50;
    """, (query_vector,))
    
    vector_results = cur.fetchall()
    
    found_in_vector = False
    match_index = -1
    print("\n--- [Top 50 Vector Search Results] ---")
    for i, row in enumerate(vector_results):
        law_full = f"{row[1]} {row[2]}"
        content_snippet = row[3][:100].replace('\n', ' ')
        is_match = expected_statute_pattern in law_full or expected_statute_pattern in row[3]
        
        if is_match:
            found_in_vector = True
            match_index = i + 1
            marker = "★ [MATCH] "
        else:
            marker = f"[{i+1:2}] "
        
        if i < 20 or is_match: # Show top 20 or the match if it's deeper
            print(f"{marker}{law_full} (Dist: {row[4]:.4f}) | {content_snippet}...")

    # 2. Keyword Search (using legal_synonyms)
    keywords = get_synonyms(original_query if original_query else query)
    print(f"\n--- [Keyword Expansion] ---")
    print(f"Keywords Extracted: {keywords}")
    
    found_in_keyword = False
    if keywords:
        for kw in keywords[:3]:
            cur.execute("SELECT id, law_name, article, content FROM statutes WHERE law_name ILIKE %s OR content ILIKE %s LIMIT 5", (f'%{kw}%', f'%{kw}%'))
            kw_results = cur.fetchall()
            for row in kw_results:
                law_full = f"{row[1]} {row[2]}"
                if expected_statute_pattern in law_full:
                    found_in_keyword = True
                    print(f"★ [KW-MATCH] Found via '{kw}': {law_full}")

    print(f"\n--- [Final Summary for {test_id}] ---")
    if found_in_vector:
        print(f"Result: FOUND in Vector Search at Rank {match_index}")
        if match_index > 20:
            print(f"Status: FAIL (Outside Top 20 Limit)")
        else:
            print(f"Status: POTENTIAL SUCCESS (Candidate was available)")
    elif found_in_keyword:
        print(f"Result: FOUND via Keyword Search")
        print(f"Status: POTENTIAL SUCCESS (Candidate was available)")
    else:
        print(f"Result: NOT FOUND in Top 50 or Keywords.")
        print(f"Status: CRITICAL FAIL (Search/Embedding Gap)")

    cur.close()
    conn.close()

# Test Cases to analyze
cases = [
    ("FRAUD_04_S", "직원이 포스기에서 고의로 현금 취소하고 돈을 챙긴 걸 CCTV로 확인했습니다.", "직원이 포스기에서 고의로 현금 취소하고 돈을 챙긴 걸 CCTV로 확인했습니다.", "제356조"),
    ("TRAFFIC_01_S", "음주운전 차량에 치였는데 범인이 현장...", "음주운전 차량에 치였는데 범인이 현장에서 도망갔어요. 뺑소니인 것 같은데 어떻게 하죠?", "제5조의3"),
    ("CRIMINAL_10_S", "집 앞에 주차 중인 제 오토바이를 누...", "집 앞에 주차 중인 제 오토바이를 누가 몰래 가져갔어요. 어떻게 신고하나요?", "제329조"),
]

if __name__ == "__main__":
    for c in cases:
        analyze_case(*c)
    print("\nAnalysis Complete.")
