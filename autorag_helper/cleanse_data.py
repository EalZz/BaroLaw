import pandas as pd
import os
import ast

QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- Data Cleansing Start ---")
if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    
    def cleanse_gt(gt_val):
        # gt_val이 [['id1']] 또는 ["['id1']"] 등 다양한 형태일 수 있음
        try:
            new_outer = []
            for item in gt_val:
                # item이 string이면 ast.literal_eval 등으로 파싱 시도
                if isinstance(item, str):
                    try:
                        inner_list = ast.literal_eval(item)
                        if isinstance(inner_list, list):
                            new_outer.append([str(x).strip(" []'") for x in inner_list])
                        else:
                            new_outer.append([str(inner_list).strip(" []'")])
                    except:
                        new_outer.append([item.strip(" []'")])
                elif isinstance(item, (list, pd.Series, pd.core.series.Series)):
                    new_outer.append([str(x).strip(" []'") for x in item])
                else:
                    new_outer.append([str(item).strip(" []'")])
            return new_outer
        except Exception as e:
            return [[str(gt_val).strip(" []'")]]

    qdf['retrieval_gt'] = qdf['retrieval_gt'].apply(cleanse_gt)
    qdf['generation_gt'] = qdf['generation_gt'].apply(lambda x: [str(item) for item in list(x)])
    
    qdf.to_parquet(QA_PATH, index=False, engine='pyarrow')
    print("Successfully cleansed IDs in qa.parquet.")
else:
    print("Files missing.")

print("--- Data Cleansing Successful ---")
