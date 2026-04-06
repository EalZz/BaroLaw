import pandas as pd
import numpy as np
import os

QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

if os.path.exists(QA_PATH):
    qdf = pd.read_parquet(QA_PATH)
    sample = qdf['retrieval_gt'].iloc[0]
    print(f"RAW VALUE: {sample}")
    print(f"VALUE TYPE: {type(sample)}")
    if isinstance(sample, (list, np.ndarray)):
        print(f"INNER SAMPLE: {sample[0]} (Type: {type(sample[0])})")
else:
    print("File not found.")
