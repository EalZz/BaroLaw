import pandas as pd
import numpy as np
import os

QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- Final Deep List Correction Start ---")
if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    
    def force_pure_list(val):
        # 어떤 형태의 리스트/배열이든 순수 Python List[List[str]]로 변환
        new_outer = []
        if isinstance(val, (list, np.ndarray, pd.Series)):
            for inner in val:
                if isinstance(inner, (list, np.ndarray, pd.Series)):
                    new_outer.append([str(x) for x in inner])
                else:
                    new_outer.append([str(inner)])
        else:
            new_outer.append([str(val)])
        return new_outer

    qdf['retrieval_gt'] = qdf['retrieval_gt'].apply(force_pure_list)
    qdf['generation_gt'] = qdf['generation_gt'].apply(lambda x: [str(item) for item in list(x)])
    
    qdf.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print("Successfully corrected retrieval_gt to pure Python List[List[str]].")
else:
    print("File missing.")

print("--- Final Deep List Correction Successful ---")
