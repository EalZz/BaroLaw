import pandas as pd
import os
import re

QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- Data Regex Cleansing Start ---")
if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    
    def super_cleanse(val):
        # val이 [['"['478']"']] 등 기괴한 형태일 수 있음
        # 모든 대괄호, 따옴표 등을 제거하고 콤마로 구분된 것들을 추출
        # 또는 정규식으로 숫자(ID)만 추출
        try:
            str_val = str(val)
            # 모든 대괄호, 싱글/더블 따옴표 제거
            clean = re.sub(r"[\[\]\'\"]", "", str_val)
            # 콤마로 분리 후 빈칸 제거된 리스트 생성
            ids = [i.strip() for i in clean.split(",") if i.strip()]
            
            # AutoRAG 규격: List[List[str]] (한 질문에 여러 정답 세트가 있을 수 있음)
            # 현재는 보통 정답 세트가 1개이므로 [[id1, id2, ...]] 형식으로 변환
            return [ids]
        except:
            return [[]]

    qdf['retrieval_gt'] = qdf['retrieval_gt'].apply(super_cleanse)
    qdf['generation_gt'] = qdf['generation_gt'].apply(lambda x: [str(item) for item in list(x)])
    
    qdf.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print("Successfully super-cleansed IDs in qa.parquet.")
else:
    print("Files missing.")

print("--- Data Regex Cleansing Successful ---")
