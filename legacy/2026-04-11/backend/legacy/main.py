from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from routers import router as chat_router
import pandas as pd
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

app = FastAPI()

# --- [RAG 추가] 서버 시작 시 검색 엔진 로드 ---
print("🚀 법률 데이터 검색기를 로드하는 중...")
df = pd.read_parquet("corpus_chunked.parquet")
documents = [
    Document(
        page_content=row['contents'],
        metadata={'parent_id': row['parent_id']}
    ) for _, row in df.iterrows()
]

# 1. 초기 넓은 검색기 (BM25)
bm25_retriever = BM25Retriever.from_documents(documents)
# 초기엔 오답을 포함하더라도 폭넓게 잡도록 k를 15개로 대폭 증가합니다.
bm25_retriever.k = 15

# 2. 정밀 재정렬기 (CrossEncoder Re-ranker) 로딩
from sentence_transformers import CrossEncoder
from reranker import CrossEncoderReranker
from langchain.retrievers import ContextualCompressionRetriever

# 한국어 다국어 검색에 탁월한 bge-m3 모델 혹은 다른 한국어 Reranker를 선택
# 'Dongjin-kr/ko-reranker' 또는 'BAAI/bge-reranker-v2-m3' 사용
print("🧠 Re-ranker AI 모델을 초기 메모리에 적재합니다 (수 분 소요됨)...")
cross_encoder_model = CrossEncoder("Dongjin-kr/ko-reranker")

# Custom Re-ranker 인터페이스 (Top 3개 결과물 채택)
reranker_compressor = CrossEncoderReranker(model=cross_encoder_model, top_n=3)

# 3. 문서 압축 체인(Contextual Compression Retriever) 결합: BM25 -> Re-ranker 
hybrid_retriever = ContextualCompressionRetriever(
    base_compressor=reranker_compressor, 
    base_retriever=bm25_retriever
)

# 최종 파이프라인(Hybrid)을 앱 상태에 넘겨줍니다. 
app.state.legal_retriever = hybrid_retriever
print("✅ 검색기 (BM25 + Reranker 파이프라인) 로드 정상 완료!")
# ------------------------------------------

# 프로메테우스 설정
Instrumentator().instrument(app).expose(app)

# 라우터 등록
app.include_router(chat_router)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Voice Chatbot API is running"}

@app.get("/ping")
async def ping():
    return {"status": "alive"}
