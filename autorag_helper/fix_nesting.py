import pandas as pd
import numpy as np
import os

QA_PATH = '/home/ksj/BaroLaw/autorag_eval/data/qa.parquet'

print("--- Final Nesting Level Correction Start ---")
if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    
    def fix_nesting(val):
        # 최종 목표: [['id1', 'id2'], ['id3']] 형태 (List[List[str]])
        new_gt = []
        try:
            # 1. 일단 리스트로 변환
            if isinstance(val, (np.ndarray, pd.Series, list)):
                raw_list = val.tolist() if hasattr(val, 'tolist') else list(val)
                
                # 2. 내부 요소가 다시 리스트인지 체크하여 한 겹씩 언팩
                for item in raw_list:
                    if isinstance(item, (list, np.ndarray)):
                        # 만약 또 리스트면 그 내부도 문자열 리스트로 변환
                        # 예: [['478']] -> ['478']
                        inner = [str(x) for x in item.tolist() if hasattr(item, 'tolist') else item]
                        if inner: new_gt.append(inner)
                    else:
                        # 만약 단일값이면 리스트로 감싸서 추가
                        # 예: '478' -> ['478']
                        if str(item).strip():
                            new_gt.append([str(item).strip()])
            else:
                new_gt = [[str(val).strip()]]
                
            # 최종 결과가 [[...]] 인지 확인하고 아니면 보정
            if not new_gt: return [[]]
            return new_gt
        except:
            return [[]]

    qdf['retrieval_gt'] = qdf['retrieval_gt'].apply(fix_nesting)
    
    qdf.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print("Successfully corrected nesting levels in qa.parquet.")
    
    # 샘플 확인
    sample = qdf['retrieval_gt'].iloc[0]
    print(f"Sample fixed: {sample} (Type sample[0]: {type(sample[0])})")
else:
    print("File missing.")

print("--- Final Nesting Level Correction Successful ---")
