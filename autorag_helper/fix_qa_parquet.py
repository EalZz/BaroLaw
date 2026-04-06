import pandas as pd
import os

# 경로 설정
QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

if os.path.exists(QA_PATH):
    print("Loading qa.parquet for fixing...")
    df = pd.read_parquet(QA_PATH)
    
    # retrieval_gt 컬럼을 순수 파이썬 리스트로 변환
    # (Parquet 로드 시 numpy ndarray로 변환되는 경우가 많음)
    df['retrieval_gt'] = df['retrieval_gt'].apply(lambda x: x.tolist() if hasattr(x, 'tolist') else list(x))
    
    # generation_gt도 동일하게 처리 (현재는 빈 문자열 리스트)
    df['generation_gt'] = df['generation_gt'].apply(lambda x: x.tolist() if hasattr(x, 'tolist') else list(x))
    
    # 재저장 (engine='pyarrow' 권장)
    df.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print(f"Successfully fixed and saved qa.parquet at {QA_PATH}")
else:
    print(f"File not found at {QA_PATH}")
