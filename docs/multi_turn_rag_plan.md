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

### Phase 28: 성능 평가 및 미세 조정 (Scheduled)
- [ ] **Full Test Run**: 120개 시나리오에 대한 전수 테스트 실시.
- [ ] **Threshold Tuning**: 검색 결과 채택을 위한 임계값 최적화.

---

## 🏁 목표 수치 (Target Metrics)
- **Turn 1 PASS**: 90% 이상
- **Turn 2 PASS**: 80% 이상
- **Total Success**: 40 / 42 시나리오 통과 (현실적 목표 95%)
