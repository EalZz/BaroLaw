import pandas as pd
import os

CORPUS_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/corpus.parquet'
QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- Data Matching Audit Start ---")
if os.path.exists(CORPUS_PATH) and os.path.exists(QA_PATH):
    cdf = pd.read_parquet(CORPUS_PATH)
    qdf = pd.read_parquet(QA_PATH)
    
    corpus_ids = set(cdf['doc_id'].tolist())
    qa_gts = qdf['retrieval_gt'].tolist()
    
    print(f"Corpus ID count: {len(corpus_ids)}")
    print(f"QA Case count: {len(qa_gts)}")
    
    # 첫 번째 케이스 샘플 분석
    sample_gt = qa_gts[0]
    print(f"Sample GT Structure: {sample_gt} (type: {type(sample_gt)})")
    
    missing_count = 0
    total_gt_ids = 0
    for case in qa_gts:
        for group in case:
            for item in group:
                total_gt_ids += 1
                if item not in corpus_ids:
                    missing_count += 1
                    if missing_count < 5:
                        print(f"  [MISSING] GT ID '{item}' not found in corpus.")
    
    print(f"\nAudit Result: {missing_count}/{total_gt_ids} IDs missing.")
    print(f"Corpus sample IDs: {list(corpus_ids)[:5]}")
else:
    print("Files missing.")
