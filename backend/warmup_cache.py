import os
import sys
import torch
import time

# 현재 디렉토리를 path에 추가하여 rag.py를 임포트 가능하게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from rag import LegalRetrieverV8, CORPUS_PATH, CACHE_PATH
    print(f"--- [v8.3.3 Warmup] Starting Golden Cache Creation ---")
    print(f" - Corpus: {CORPUS_PATH}")
    print(f" - Target: {CACHE_PATH}")
    
    start_time = time.time()
    
    # 싱글톤 인스턴스 초기화 및 인코딩 강제 실행
    retriever = LegalRetrieverV8()
    retriever.initialize()
    
    elapsed = time.time() - start_time
    print(f"\n--- [v8.3.3 Warmup] Success! ---")
    print(f" - Size: {len(retriever.corpus_embeddings)} items")
    print(f" - Time: {elapsed:.1f}s")
    print(f" - Device: {retriever.model.device}")
    print(f"이제 서버를 다시 켜거나 테스트를 실행하면 즉각 응답합니다.")

except Exception as e:
    print(f"--- [v8.3.3 Warmup] Failed: {e} ---")
    sys.exit(1)
