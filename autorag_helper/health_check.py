import pandas as pd
import numpy as np
import os

CORPUS_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/corpus.parquet'
QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- Data Health Check Start ---")
if os.path.exists(CORPUS_PATH) and os.path.exists(QA_PATH):
    cdf = pd.read_parquet(CORPUS_PATH)
    qdf = pd.read_parquet(QA_PATH)
    
    # 1. 중복 체크
    dup_count = cdf.duplicated(subset=['doc_id']).sum()
    print(f"Corpus Duplicates: {dup_count}")
    if dup_count > 0:
        print(f"  Sample duplicate IDs: {cdf[cdf.duplicated(subset=['doc_id'])]['doc_id'].head(3).tolist()}")
        
    # 2. QA 정답 매칭 최종 검증
    all_corpus_ids = set(cdf['doc_id'].astype(str).tolist())
    match_fail = 0
    for idx, row in qdf.iterrows():
        for group in row['retrieval_gt']:
            for gid in group:
                if str(gid) not in all_corpus_ids:
                    match_fail += 1
                    if match_fail < 3:
                        print(f"  [MISS] QA-{row['qid']} GT-ID '{gid}' not in Corpus.")
    
    print(f"Match Fail Count: {match_fail}")
    
    # 3. 데이터 타입 구조 실체 확인
    sample_gt = qdf['retrieval_gt'].iloc[0]
    print(f"Sample GT: {sample_gt} (Type: {type(sample_gt)})")
    if len(sample_gt) > 0:
        print(f"  First Inner Type: {type(sample_gt[0])}")
        if len(sample_gt[0]) > 0:
            print(f"    Item Type: {type(sample_gt[0][0])}")
else:
    print("Files missing.")

print("--- Data Health Check Finished ---")
