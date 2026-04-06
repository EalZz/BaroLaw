import pandas as pd
try:
    from rank_bm25 import BM25Okapi
    print("--- [PASS] rank_bm25 imported ---")
    
    # 샘플 데이터로 인덱싱 시도
    corpus = [["hello", "world"], ["this", "is", "test"]]
    bm25 = BM25Okapi(corpus)
    print("--- [PASS] BM25Okapi initialized successfully ---")
    
    # 실제 코퍼스 데이터로 인덱싱 시도
    CORPUS_PATH = '/home/ksj/BaroLaw/autorag_eval/data/corpus_minimal.parquet'
    df = pd.read_parquet(CORPUS_PATH)
    tokenized_corpus = [doc.split() for doc in df['contents'].tolist()]
    print(f"Tokenizing {len(tokenized_corpus)} docs...")
    bm25_real = BM25Okapi(tokenized_corpus)
    print("--- [PASS] Real BM25 indexing SUCCESSFUL ---")
    
except Exception as e:
    print(f"--- [FAIL] BM25 Debug Error: {e} ---")
    import traceback
    traceback.print_exc()
