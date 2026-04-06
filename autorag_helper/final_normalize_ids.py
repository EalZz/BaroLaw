import pandas as pd
import os

# 경로 설정
CORPUS_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/corpus.parquet'
QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- Final ID Normalization Start ---")

# 1. Corpus 데이터 정규화
if os.path.exists(CORPUS_PATH):
    cdf = pd.read_parquet(CORPUS_PATH)
    cdf['doc_id'] = cdf['doc_id'].astype(str)
    cdf.to_parquet(CORPUS_PATH, index=False, engine='pyarrow')
    print(f"Corpus doc_id normalized to String. Total: {len(cdf)}")

# 2. QA 데이터 정규화
if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    # retrieval_gt 내부의 모든 요소를 문자열로 변환
    qdf['retrieval_gt'] = qdf['retrieval_gt'].apply(lambda gt_list: [[str(item) for item in group] if isinstance(group, list) else [str(group)] for group in gt_list])
    # generation_gt 확인
    qdf['generation_gt'] = qdf['generation_gt'].apply(lambda x: [str(item) for item in list(x)])
    
    qdf.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print(f"QA retrieval_gt/generation_gt normalized. Total: {len(qdf)}")

print("--- Data Normalization Successful ---")
