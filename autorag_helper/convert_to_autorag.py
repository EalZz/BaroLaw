import json
import os
import sys
import pandas as pd
import re
from collections import Counter, defaultdict

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAW_MAPPING_PATH = os.path.join(BASE_DIR, 'backend', 'law_mapping.json')
GOLDEN_DATASET_PATH = os.path.join(BASE_DIR, 'tests', 'golden_dataset.json')
OUTPUT_DIR = os.path.join(BASE_DIR, 'autorag_eval', 'autorag_data')
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'qa.parquet')

def normalize(name):
    if not name: return ""
    name = re.sub(r'\(.*?\)', '', name)
    return name.strip()

def convert_to_autorag():
    if not os.path.exists(LAW_MAPPING_PATH):
        print(f"[ERROR] law_mapping.json not found.")
        sys.exit(1)
        
    with open(LAW_MAPPING_PATH, 'r', encoding='utf-8') as f:
        law_mapping = json.load(f)
    print(f"Loaded {len(law_mapping)} mappings.")

    with open(GOLDEN_DATASET_PATH, 'r', encoding='utf-8') as f:
        golden_data = json.load(f)

    norm_mapping = defaultdict(list)
    for raw_name, id_str in law_mapping.items():
        nm = normalize(raw_name)
        if nm: norm_mapping[nm].append(id_str)

    qa_list = []
    
    for entry in golden_data:
        test_id = entry.get('test_id', 'unknown')
        for turn in entry.get('turns', []):
            qid = f"{test_id}_T{turn.get('turn_id', 1)}"
            query = turn.get('user_input', '')
            statutes = turn.get('expected_statutes', [])
            
            gt_ids = set()
            for name in statutes:
                clean_name = name.strip()
                if clean_name in law_mapping:
                    gt_ids.add(law_mapping[clean_name])
                else:
                    nm = normalize(clean_name)
                    if nm in norm_mapping:
                        for mapped_id in norm_mapping[nm]:
                            gt_ids.add(mapped_id)
            
            if gt_ids:
                qa_list.append({
                    'qid': qid,
                    'query': query,
                    'retrieval_gt': [list(gt_ids)],
                    'generation_gt': [''] # 추가: AutoRAG 필수 컬럼 (List[str] 형태)
                })

    if qa_list:
        df = pd.DataFrame(qa_list)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        df.to_parquet(OUTPUT_PATH, index=False, engine='pyarrow')
        print(f"Successfully converted {len(qa_list)} items with 'generation_gt' column to {OUTPUT_PATH}")
    else:
        print("No valid queries to save.")

if __name__ == "__main__":
    convert_to_autorag()
