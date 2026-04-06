import pandas as pd
import os

CORPUS_PATH = '/home/ksj/BaroLaw/autorag_eval/data/corpus_minimal.parquet'

if os.path.exists(CORPUS_PATH):
    print(f"Loading {CORPUS_PATH} for cleanup...")
    df = pd.read_parquet(CORPUS_PATH)
    
    # 1. doc_id와 contents에서 NaN 제거
    df['doc_id'] = df['doc_id'].fillna("unknown_id").astype(str)
    df['contents'] = df['contents'].fillna("empty_content").astype(str)
    
    # 2. 공백 문자열 처리
    df['contents'] = df['contents'].apply(lambda x: x if x.strip() else "empty_content")
    
    # 3. doc_id 중복 제거 (보험용)
    df = df.drop_duplicates(subset=['doc_id'])
    
    df.to_parquet(CORPUS_PATH, index=False, engine='pyarrow')
    print(f"Successfully cleaned up corpus at {CORPUS_PATH}. Total rows: {len(df)}")
else:
    print(f"File missing at {CORPUS_PATH}")
