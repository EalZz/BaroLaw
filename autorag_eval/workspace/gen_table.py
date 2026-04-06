import pandas as pd
import os

BASE_DIR = os.path.expanduser('~/BaroLaw/autorag_eval/autorag_data')
QA_HARD_PATH = os.path.join(BASE_DIR, 'qa_hard.parquet')
CORPUS_PATH = os.path.join(BASE_DIR, 'corpus.parquet')
OUTPUT_MD = os.path.expanduser('~/BaroLaw/autorag_eval/workspace/hard_query_comparison.md')

qa_df = pd.read_parquet(QA_HARD_PATH)
corpus_df = pd.read_parquet(CORPUS_PATH)
corpus_map = dict(zip(corpus_df['doc_id'], corpus_df['contents']))

with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
    f.write('# BaroLaw 가혹 쿼리(Hard Query) 상세 검증 리스트 (100건)\n\n')
    f.write('이 표는 변조된 질문이 실제 어떤 법적 근거(정답)를 찾아야 하는지 명시합니다.\n\n')
    f.write('| ID | 변조된 질문 (Hard) | 정답 근거 (Ground Truth) |\n')
    f.write('| :--- | :--- | :--- |\n')
    
    for idx, row in qa_df.iterrows():
        gt_id = row['retrieval_gt'][0][0]
        # Clean ground truth: replace all newlines with spaces and condense spaces
        orig_gt = corpus_map.get(gt_id, '정답 없음')
        gt_content = ' '.join(orig_gt.replace('\n', ' ').replace('\r', ' ').replace('|', 'ㅣ').split())
        
        if len(gt_content) > 150:
            gt_content = gt_content[:147] + '...'
            
        query = ' '.join(row['query'].replace('\n', ' ').replace('\r', ' ').replace('|', 'ㅣ').split())
        f.write(f'| {idx+1} | {query} | {gt_content} |\n')

print('GENERATION_COMPLETE')
