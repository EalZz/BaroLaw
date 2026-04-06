import pandas as pd
from autorag.nodes.lexicalretrieval import bm25
import os

# 데이터 경로
CORPUS_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/corpus.parquet'
QA_PATH = '/home/ksj/BaroLaw/autorag_eval/autorag_data/qa.parquet'

print("--- BM25 Direct Testing Start ---")
try:
    print("Loading datasets...")
    corpus_df = pd.read_parquet(CORPUS_PATH)
    qa_df = pd.read_parquet(QA_PATH)
    
    print(f"Corpus size: {len(corpus_df)}")
    print(f"QA size: {len(qa_df)}")
    
    # BM25 모듈 테스트 (직접 초기화 시도)
    # 실제 AutoRAG가 내부에서 호출하는 함수 시그니처와 매칭 시도
    # Note: 버전 0.3.x 마다 pure 함수의 인자가 다를 수 있음
    print("Initializing BM25 logic...")
    # 여기서 실패하면 토크나이저나 리소스 로딩 문제임
    
    # 0.3.21 버전의 BM25 노드를 시뮬레이션
    from autorag.nodes.lexicalretrieval.bm25 import bm25 as bm25_module
    
    # evaluate가 하는 일 수행
    # queries = qa_df['query'].tolist()
    # 결과가 나오는지 확인
    print("Pre-flight check successful. Now capturing real error by simulating full run...")
    
except Exception as e:
    print(f"\n[CRITICAL ERROR] {e}")
    import traceback
    traceback.print_exc()
