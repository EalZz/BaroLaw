# BaroLaw RAG v4.0 Evolution Plan (Updated)

이 문서는 RAG v3.x의 한계를 극복하고, Pydantic AI 기반 의도 분석과 모듈화된 RAG 엔진을 통해 성능을 극대화하기 위한 계획입니다.

---

## 🏗️ v4.0 핵심 아키텍처 (Strategic Shift)
1. **Reranker Migration**: `BAAI/bge-reranker-v2-m3` 모델로 업그레이드.
2. **Hybrid Search Integration**: Vector Search + BM25 키워드 검색 결합.
3. **Modular Pipeline**: `rag.py`를 Retriever와 Scorer로 분리하여 유지보수성 향상.
4. **Pydantic AI Preprocessor**: `preprocessor.py`를 통해 사용자 의도 및 법률 키워드를 정밀하게 추출.

---

## 📅 로드맵 및 단계별 과제

### Phase 26: Pydantic AI 기반 의도 분석 (Resolved)
- [x] **Typed Intent Extraction**: `LegalIntent` 스키마를 정의하여 카테고리, 키워드, 사실요약을 구조화.
- [x] **Fallback L2 Implementation**: 질문이 모호할 경우 AI가 역질문을 던지도록 설계.
- [x] **JSON Robustness**: Ollama 출력의 불확실성을 해결하기 위해 RegEx 기반 Fallback 파싱 구현.

### Phase 27: RAG Lockdown & Scoring Optimization (Resolved)
- [x] **Modular Scorer**: `LegalScorer` 클래스를 통해 스코어링 로직을 캡슐화.
- [x] **Negative Scoring**: 세션 카테고리와 일치하지 않는 검색 결과에 페널티(0.8x) 부여.
- [x] **Category Boosting**: 질문과 카테고리의 유사도가 높을 때 가산점(0.35) 부여.
- [x] **Keyword Weighting**: LLM이 추출한 전문 법률 키워드에 높은 가중치 할당.

### Phase 28: 하이브리드 리트리버 기반 정밀 최적화 (Resolved)
- [x] **AutoRAG Calibration**: 101개 가중치 스윕을 통해 렉시컬/시멘틱 최적의 배합비(0.49) 도출.
- [x] **Top-k Narrowing**: `top_k: 1~3` 압축 타격을 통해 정답이 항상 1순위에 노출되도록 보정.
- [x] **F1 Performance**: 10개 시나리오 대조군 기준 F1 1.0 달성.

### Phase 29: 상담 품질 및 출력 포맷 최적화 (Scheduled)
- [ ] **Naive Consultation Tone**: 법률 용어 나열보다 일상어 기반 상담에 집중 (LLM 독해 품질 튜닝).
- [ ] **Interface Preservation**: 규칙 2번 및 `app.py:283` 규격에 의거, **`---[LEGAL_DETAILS]---`** 및 **`---[LEGAL_BASIS]---`** 태그를 통한 분리 형식 절대 엄수.
- [ ] **Top-k Robustness**: `top_k: 1` 뿐만 아니라 **`1~5`** 범위의 최적화를 통해 리트리버 실패 예외 케이스(Edge Cases) 최소화.

---

## 🏁 목표 수치 (Target Metrics)
- **Retrieval Match (Recall@1)**: 95% 이상
- **Consultation Quality (F1/G-Eval)**: 90% 이상
- **Total Pipeline Success**: 모든 시나리오 통과 및 사용자 신뢰성 확보
