# MVP RAG 시스템 파이프라인 설계

**버전**: v1.0  
**작성일**: 2025-03-25  
**기준**: AutoRAG Trial 27 최적화 결과  

---

## 1. 개요

### 1.1 목표
AutoRAG 최적화 결과를 바탕으로 **MVP 단계에서 사용할 수 있는 안정적이고 성능이 검증된 RAG 파이프라인**을 설계합니다.

### 1.2 최적화 기반 (AutoRAG Trial 27)

| 모듈 | 최적화 파라미터 | 성능 |
|------|----------------|------|
| **BM25** | `ko_kiwi` 토크나이저, top_k=5 | F1: -, Recall: - |
| **VectorDB** | `barolaw_vector`, top_k=5 | F1: -, Recall: - |
| **HybridRRF** | target=vectordb, weight=4.0, top_k=1 | **F1: 1.0, Recall: 1.0** |

> **최종 선택**: HybridRRF (Reciprocal Rank Fusion)

---

## 2. 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Request                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Query Preprocessor                               │
│  • 형태소 분석 (ko_kiwi)                                                 │
│  • 불용어 처리                                                           │
│  • 동의어 확장 (legal_synonyms)                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Retrieval Pipeline (HybridRRF)                       │
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐                           │
│  │   BM25 Search  │     │ Vector Search    │                           │
│  │  (ko_kiwi)     │     │ (ko-sroberta)    │                           │
│  │  top_k: 5      │     │  top_k: 5         │                           │
│  └────────┬────────┘     └────────┬────────┘                           │
│           │                       │                                      │
│           └───────────┬───────────┘                                      │
│                       ▼                                                  │
│           ┌───────────────────────┐                                       │
│           │   RRF Fusion         │                                       │
│           │   weight=4.0         │                                       │
│           │   top_k=1            │                                       │
│           └───────────┬───────────┘                                      │
│                       │                                                  │
│                       ▼                                                  │
│           ┌───────────────────────┐                                       │
│           │  Ranked Results       │                                       │
│           │  (Statutes + Q&A)     │                                       │
│           └───────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Context Builder                                    │
│  • 상위 10개 결과 선별                                                   │
│  • 법령 맥락 서식화                                                      │
│  • 중복 제거                                                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          LLM Input                                       │
│  • System Prompt + Context + User Query                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 컴포넌트 상세 설계

### 3.1 Query Preprocessor

```python
class QueryPreprocessor:
    """MVP: 간단한 전처리만 수행"""
    
    def __init__(self):
        from kiwipiepy import Kiwi
        self.kiwi = Kiwi()
        self.stopwords = load_legal_stopwords()  # 법령 전용 불용어
        
    def process(self, query: str) -> Dict:
        # 1. 형태소 분석
        tokens = self.kiwi.tokenize(query)
        
        # 2. 명사/용언만 추출
        legal_tokens = [
            t.form for t in tokens 
            if t.tag in ('NNG', 'NNP', 'VV', 'VA', 'XR')
            and t.form not in self.stopwords
        ]
        
        # 3. 동의어 확장
        extended = expand_synonyms(legal_tokens)
        
        return {
            "original": query,
            "tokens": legal_tokens,
            "extended_tokens": extended
        }
```

### 3.2 BM25 Retriever (ko_kiwi 토크나이저)

```python
class BM25Retriever:
    """AutoRAG 최적화: ko_kiwi 토크나이저 적용"""
    
    def __init__(self, corpus: List[Dict], top_k: int = 5):
        from kiwipiepy import Kiwi
        from rank_bm25 import BM25Okapi
        
        self.kiwi = Kiwi()
        self.top_k = top_k
        
        # 코퍼스 토크나이징 (ko_kiwi)
        self.corpus = corpus
        self.corpus_tokens = [
            self._tokenize(item['contents']) 
            for item in corpus
        ]
        
        self.bm25 = BM25Okapi(self.corpus_tokens)
        
    def _tokenize(self, text: str) -> List[str]:
        """ko_kiwi形态素分析"""
        tokens = self.kiwi.tokenize(text)
        return [
            t.form for t in tokens
            if t.tag in ('NNG', 'NNP', 'VV', 'VA', 'XR')
        ]
    
    def search(self, query: str) -> List[Tuple[int, float]]:
        """검색 수행"""
        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        
        # top_k 개 선택
        top_indices = np.argsort(scores)[::-1][:self.top_k]
        return [(idx, scores[idx]) for idx in top_indices]
```

### 3.3 Vector Retriever

```python
class VectorRetriever:
    """Semantic Search using ko-sroberta-multitask"""
    
    def __init__(self, corpus: List[Dict], top_k: int = 5):
        import torch
        from sentence_transformers import SentenceTransformer
        
        self.corpus = corpus
        self.top_k = top_k
        
        # 모델 로드 (캐시 사용)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=device)
        
        # 임베딩 캐시 로드
        self.embeddings = load_embeddings_cache()  # corpus_embeddings.pt
        
    def search(self, query: str) -> List[Tuple[int, float]]:
        """유사도 검색"""
        query_emb = self.model.encode(query, convert_to_tensor=True)
        
        # cosine similarity
        cos_scores = torch.nn.functional.cosine_similarity(
            query_emb, self.embeddings
        ).cpu().numpy()
        
        top_indices = np.argsort(cos_scores)[::-1][:self.top_k]
        return [(idx, cos_scores[idx]) for idx in top_indices]
```

### 3.4 HybridRRF Fusion

```python
class HybridRRF:
    """Reciprocal Rank Fusion - AutoRAG Trial 27 최적화 결과"""
    
    def __init__(self, weight: float = 4.0, top_k: int = 1):
        self.weight = weight  # AutoRAG: 4.0
        self.top_k = top_k    # AutoRAG: 1
        
    def fuse(self, 
             bm25_results: List[Tuple[int, float]], 
             vector_results: List[Tuple[int, float]]) -> List[int]:
        """RRF fusion 수행"""
        
        # RRF 점수 계산
        rrf_scores = defaultdict(float)
        
        # BM25 결과 순위
        for rank, (idx, score) in enumerate(bm25_results, 1):
            rrf_scores[idx] += 1.0 / (rank ** self.weight)
            
        # Vector 결과 순위
        for rank, (idx, score) in enumerate(vector_results, 1):
            rrf_scores[idx] += 1.0 / (rank ** self.weight)
        
        # 정렬
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [idx for idx, score in ranked[:self.top_k * 10]]  # 최종 top_k * 10 반환
```

### 3.5 Context Builder

```python
class ContextBuilder:
    """RAG 결과를 컨텍스트로 변환"""
    
    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        
    def build(self, 
              corpus: List[Dict], 
              fused_indices: List[int]) -> Dict:
        """법령 컨텍스트 생성"""
        
        results = []
        seen = set()
        
        for idx in fused_indices[:self.max_results]:
            item = corpus[idx]
            meta = item.get('metadata', {})
            
            # 중복 제거 (law_name + article 기준)
            key = f"{meta.get('law_name')}_{meta.get('article')}"
            if key in seen:
                continue
            seen.add(key)
            
            results.append({
                "id": item.get('doc_id'),
                "law_name": meta.get('law_name'),
                "article": meta.get('article'),
                "content": item.get('contents'),
                "metadata": meta
            })
        
        return {
            "statutes": results,
            "qa": []  # MVP: Q&A는 제외
        }
```

---

## 4. 파이프라인 통합

```python
class LegalRAGPipeline:
    """MVP RAG 파이프라인 (AutoRAG Trial 27 최적화 적용)"""
    
    # AutoRAG Trial 27 최적화 파라미터
    BM25_TOP_K = 5
    VECTOR_TOP_K = 5
    RRF_WEIGHT = 4.0
    RRF_TOP_K = 1
    FINAL_TOP_K = 10
    
    def __init__(self):
        self.preprocessor = QueryPreprocessor()
        self.bm25_retriever = None
        self.vector_retriever = None
        self.rrf_fusion = HybridRRF(weight=self.RRF_WEIGHT, top_k=self.RRF_TOP_K)
        self.context_builder = ContextBuilder(max_results=self.FINAL_TOP_K)
        
    def initialize(self):
        """코퍼스 로드 및 인덱스 구축"""
        logger.info("--- [MVP-RAG] Initializing Pipeline ---")
        
        # 코퍼스 로드
        corpus = load_corpus()
        
        # BM25 인덱스 (ko_kiwi)
        self.bm25_retriever = BM25Retriever(corpus, top_k=self.BM25_TOP_K)
        
        # Vector 인덱스
        self.vector_retriever = VectorRetriever(corpus, top_k=self.VECTOR_TOP_K)
        
        self.corpus = corpus
        logger.info(f"--- [MVP-RAG] Ready (Corpus: {len(corpus)}) ---")
        
    def search(self, query: str) -> Dict:
        """검색 실행"""
        # 1. 쿼리 전처리
        processed = self.preprocessor.process(query)
        
        # 2. BM25 검색
        bm25_results = self.bm25_retriever.search(processed['original'])
        
        # 3. Vector 검색
        vector_results = self.vector_retriever.search(processed['original'])
        
        # 4. RRF Fusion
        fused_indices = self.rrf_fusion.fuse(bm25_results, vector_results)
        
        # 5. 컨텍스트 생성
        context = self.context_builder.build(self.corpus, fused_indices)
        
        return context
```

---

## 5. 설정값 요약

### AutoRAG Trial 27 → MVP 적용

| 파라미터 | AutoRAG 최적화 | MVP 설계 | 비고 |
|----------|---------------|----------|------|
| **BM25 토크나이저** | `ko_kiwi` | `ko_kiwi` | ✅ 적용 |
| **BM25 top_k** | 5 | 5 | ✅ 적용 |
| **Vector top_k** | 5 | 5 | ✅ 적용 |
| **RRF weight** | 4.0 | 4.0 | ✅ 적용 |
| **RRF top_k** | 1 | 1 | ✅ 적용 |
| **target_modules** | vectordb | bm25 + vectordb | ✅ 적용 |
| **최종 결과 수** | - | 10 | MVP 확장 |

---

## 6. API 인터페이스

```python
# backend/rag.py (새로운 인터페이스)

def search_relevant_context(
    query: str,
    original_query: str = None,
    turn_count: int = 1,
    llm_keywords: List[str] = None,
    session_category: str = None,
    prev_statute_names: List[str] = None
) -> Dict[str, Any]:
    """
    MVP RAG 검색
    
    Returns:
        {
            "statutes": [
                {"id": "...", "law_name": "...", "article": "...", "content": "..."}
            ],
            "qa": []  # MVP: 빈 배열
        }
    """
    pipeline = LegalRAGPipeline.get_instance()
    return pipeline.search(query)
```

---

## 7. 테스트 전략

### 7.1 단위 테스트

| 모듈 | 테스트 항목 |
|------|------------|
| QueryPreprocessor | 형태소 분석 정확성, 불용어 제거, 동의어 확장 |
| BM25Retriever | ko_kiwi 토크나이징, 점수 순위 |
| VectorRetriever | 임베딩 생성, 유사도 계산 |
| HybridRRF | Fusion 알고리즘, 순위 결합 |
| ContextBuilder | 중복 제거, 최대 개수 제한 |

### 7.2 통합 테스트

| 시나리오 | 예상 결과 |
|----------|----------|
| 법령명 검색 | 해당 법령 상위 노출 |
| 법률 용어 검색 | 관련 법령 다수 반환 |
| 모호한 질문 | RRF로 인한 다양성 확보 |

### 7.3 성능 벤치마크

| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| 검색 지연시간 | < 100ms | time.time() 차분 |
| Cold Start | < 3초 | 첫 요청 측정 |
| 임베딩 캐시 적중률 | > 90% | 로그 분석 |

---

## 8. 구현 체크리스트

- [ ] `kiwipiepy` 의존성 추가
- [ ] `QueryPreprocessor` 클래스 구현
- [ ] `BM25Retriever` ko_kiwi 적용
- [ ] `VectorRetriever` 임베딩 캐시 연동
- [ ] `HybridRRF` fusion 로직 구현
- [ ] `ContextBuilder` 중복 제거 로직
- [ ] `LegalRAGPipeline` 통합
- [ ] 단위 테스트 작성
- [ ] 성능 벤치마크 측정

---

## 9. 참고 문서

- AutoRAG Trial 27 결과: `autorag_eval/final_victory_27.csv`
- AutoRAG 설정: `autorag_eval/autorag_config.yaml`
- 현재 rag.py: `backend/rag.py`

---

**작성자**: Sisyphus  
**최종 수정**: 2025-03-25
