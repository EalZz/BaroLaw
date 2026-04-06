import pandas as pd
import os

BASE_DIR = os.path.expanduser('~/BaroLaw/autorag_eval/autorag_data')
QA_PATH = os.path.join(BASE_DIR, 'qa.parquet')
QA_HARD_PATH = os.path.join(BASE_DIR, 'qa_hard.parquet')
CORPUS_PATH = os.path.join(BASE_DIR, 'corpus.parquet')
OUTPUT_MD = os.path.expanduser('~/BaroLaw/autorag_eval/workspace/hard_query_comparison.md')

# 데이터 로드
qa_df = pd.read_parquet(QA_PATH)
qa_hard_df = pd.read_parquet(QA_HARD_PATH)
corpus_df = pd.read_parquet(CORPUS_PATH)
corpus_map = dict(zip(corpus_df['doc_id'], corpus_df['contents']))

# QA_HARD의 각 행에 대해, 동일한 retrieval_gt를 가진 원본 QA 행을 매칭
# (retrieval_gt는 리스트 형태이므로 해시 가능한 튜플로 변환하여 매칭)
qa_df['gt_tuple'] = qa_df['retrieval_gt'].apply(lambda x: tuple(x[0]))
qa_hard_df['gt_tuple'] = qa_hard_df['retrieval_gt'].apply(lambda x: tuple(x[0]))

# 매칭 테이블 생성
merged = pd.merge(
    qa_hard_df[['query', 'gt_tuple']], 
    qa_df[['query', 'gt_tuple']], 
    on='gt_tuple', 
    suffixes=('_hard', '_orig')
).drop_duplicates('query_hard') # 중복 매칭 방지

with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
    f.write('# BaroLaw 가혹 쿼리(Hard Query) 상세 검증 리스트 (100건)\n\n')
    f.write('| ID | 원본 질문 (Original) | 변조된 질문 (Hard) | 정답 근거 (Answer) |\n')
    f.write('| :--- | :--- | :--- | :--- |\n')
    
    for idx, (idx_row, row) in enumerate(merged.iterrows()):
        gt_id = row['gt_tuple'][0]
        gt_content = corpus_map.get(gt_id, '정답 없음').replace('\n', ' ').replace('\r', '').strip()
        gt_content = ' '.join(gt_content.split())
        if len(gt_content) > 150:
            gt_content = gt_content[:147] + '...'
            
        orig_q = ' '.join(row['query_orig'].replace('\n', ' ').replace('|', 'ㅣ').split())
        hard_q = ' '.join(row['query_hard'].replace('\n', ' ').replace('|', 'ㅣ').split())
        
        f.write(f'| {idx+1} | {orig_q} | {hard_q} | {gt_content} |\n')

print('SUCCESS')
