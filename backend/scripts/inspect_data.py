import pandas as pd
import os

STATUTE_DIR = "/home/ksj/voice-chatbot-toy/backend/data/statute"

with open("/home/ksj/voice-chatbot-toy/backend/data/verification.txt", "w", encoding="utf-8") as f:
    total = 0
    for fname in sorted(os.listdir(STATUTE_DIR)):
        if not fname.endswith(".parquet"):
            continue
        path = os.path.join(STATUTE_DIR, fname)
        df = pd.read_parquet(path)
        topic = fname.replace(".parquet", "")
        f.write(f"=== {topic.upper()} ({len(df)}개 조문) ===\n")
        f.write(f"  컬럼: {list(df.columns)}\n")
        f.write(f"  포함 법령: {list(df['법령명'].unique())}\n")
        f.write(f"\n  [샘플 3개]\n")
        for i, row in df.head(3).iterrows():
            content = str(row['내용'])[:150]
            f.write(f"  - {row['조문']}: {content}\n")
        f.write(f"\n")
        total += len(df)
    
    f.write(f"=== 총 합계: {total}개 조문 ===\n")

print("Done: verification.txt")
