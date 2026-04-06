import pandas as pd
import os

files = ['qa.parquet', 'corpus.parquet']
base_dir = '/home/ksj/BaroLaw/autorag_eval/autorag_data'

for f in files:
    path = os.path.join(base_dir, f)
    print(f"\n[{f}]")
    if os.path.exists(path):
        try:
            df = pd.read_parquet(path)
            print(f"  Rows: {len(df)}")
            print(f"  Cols: {df.columns.tolist()}")
            if f == 'qa.parquet':
                print(f"  Sample qid: {df['qid'][0]}")
            else:
                print(f"  Sample id: {df['doc_id'][0]}")
        except Exception as e:
            print(f"  Error reading {f}: {e}")
    else:
        print(f"  Not found at {path}")
