import pandas as pd
import glob
import os

count_data = []
for f in glob.glob('data/guide/*.parquet'):
    df = pd.read_parquet(f)
    count_data.append({'topic': os.path.basename(f), 'count': len(df)})

df_counts = pd.DataFrame(count_data)
print(df_counts.to_string(index=False))
print(f"\nTotal Items: {df_counts['count'].sum()}")
