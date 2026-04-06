import pandas as pd
import numpy as np
import os

QA_PATH = '/home/ksj/BaroLaw/autorag_eval/data/qa.parquet'

print("--- Nesting Correction V2 Start ---")
if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    
    def fix_nesting_robust(val):
        final_list = []
        try:
            # 1. 최상위 레벨 리스트화
            if isinstance(val, (list, np.ndarray, pd.Series)):
                outer_list = list(val)
                for inner in outer_list:
                    # 2. 내부 요소가 리스트/배열인 경우 정규화
                    if isinstance(inner, (list, np.ndarray, pd.Series)):
                        # 중첩 리스트의 요소를 하나씩 문자열로 추출
                        # 예: ['478'] 혹은 [['478']]에서 '478'만 남기기
                        content = []
                        inner_iter = list(inner)
                        for item in inner_iter:
                            # 3. 비정상적인 추가 중첩이 더 있으면 한 번 더 풀어줌
                            if isinstance(item, (list, np.ndarray)):
                                content.extend([str(x).strip(" []'") for x in list(item)])
                            else:
                                if str(item).strip():
                                    content.append(str(item).strip(" []'"))
                        if content: final_list.append(content)
                    else:
                        # 단일값일 경우 리스트로 감싸서 추가
                        if str(inner).strip():
                            final_list.append([str(inner).strip(" []'")])
            else:
                final_list = [[str(val).strip(" []'")]]
            
            # 최종 정규화: [[id1, id2, ...]]
            if not final_list: return [[]]
            return final_list
        except:
            return [[]]

    qdf['retrieval_gt'] = qdf['retrieval_gt'].apply(fix_nesting_robust)
    qdf.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print("Successfully corrected nesting levels to List[List[str]].")
    
    # 샘플 실체 출력 (정지용)
    sample = qdf['retrieval_gt'].iloc[0]
    print(f"SAMPLE FIXED: {sample} (Inner[0] type: {type(sample[0])})")
else:
    print("QA file missing.")

print("--- Nesting Correction V2 Successful ---")
