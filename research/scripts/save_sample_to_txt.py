import pandas as pd

def save_sample():
    try:
        df = pd.read_parquet('data/guide/estate_qa.parquet')
        if not df.empty:
            with open('sample_view.txt', 'w', encoding='utf-8') as f:
                f.write(df.iloc[0]['answer'])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    save_sample()
