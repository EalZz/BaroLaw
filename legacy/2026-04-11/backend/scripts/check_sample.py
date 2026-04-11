import pandas as pd
import json

def show_sample():
    df = pd.read_parquet('data/guide/estate_qa.parquet')
    sample = df.iloc[0].to_dict()
    
    print("-" * 50)
    print(f"Topic: {sample['topic']}")
    print(f"Question: {sample['question']}")
    print("-" * 50)
    print("Answer Content:")
    print(sample['answer'])
    print("-" * 50)
    print(f"Source: {sample['source_url']}")

if __name__ == "__main__":
    show_sample()
