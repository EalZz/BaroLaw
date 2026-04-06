import pandas as pd
import os

CORPUS_PATH = '/home/ksj/BaroLaw/autorag_eval/data/corpus.parquet'
OUTPUT_PATH = '/home/ksj/BaroLaw/autorag_eval/data/corpus_minimal.parquet'

if os.path.exists(CORPUS_PATH):
    print(f"Loading {CORPUS_PATH}...")
    df = pd.read_parquet(CORPUS_PATH)
    # metadata에 더미 필드 추가 (PyArrow Empty Struct 에러 방지용)
    df['metadata'] = [{'is_statute': 1} for _ in range(len(df))]
    df.to_parquet(OUTPUT_PATH, index=False, engine='pyarrow')
    print(f"Successfully created {OUTPUT_PATH}")
else:
    print(f"Corpus not found at {CORPUS_PATH}")
