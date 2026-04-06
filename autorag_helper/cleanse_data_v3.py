import pandas as pd
import numpy as np
import os
import re

QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- Data Recursive Unpacking Start ---")
if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    
    def recursive_get_ids(val):
        ids = []
        
        def extract(obj):
            if isinstance(obj, (list, np.ndarray, pd.Series)):
                for item in obj:
                    extract(item)
            elif isinstance(obj, str):
                # 문자열 내부에 '[' 가 있으면 다시 그 안을 봐줌
                if '[' in obj:
                    # 모든 대괄호, 따옴표 제거 후 숫자만 추출
                    clean = re.sub(r"[\[\]\'\"]", "", obj)
                    for part in clean.split(","):
                        if part.strip() and not part.strip().startswith("array") and not "dtype" in part:
                            ids.append(part.strip())
                else:
                    if obj.strip() and not obj.strip().startswith("array") and not "dtype" in obj:
                        ids.append(obj.strip())
            else:
                ids.append(str(obj))

        extract(val)
        # 중복 제거 및 리스트의 리스트로 반환
        unique_ids = list(set([i for i in ids if i]))
        return [unique_ids]

    qdf['retrieval_gt'] = qdf['retrieval_gt'].apply(recursive_get_ids)
    qdf['generation_gt'] = qdf['generation_gt'].apply(lambda x: [str(item) for item in list(x)])
    
    qdf.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print("Successfully unpacked and fixed IDs in qa.parquet.")
else:
    print("Files missing.")

print("--- Data Recursive Unpacking Successful ---")
