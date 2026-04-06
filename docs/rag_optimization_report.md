# BaroLaw RAG Optimization Report (Phase 27)

## 📊 최적화 요약
- **적용 단계**: Phase 26 ~ 27
- **핵심 변경**: Pydantic AI 기반 전처리 도입 및 RAG 엔진 모듈화 (Lockdown Strategy)
- **주요 성과**: 키워드 오염 방지 및 도메인 정밀도 향상

## 🛠️ 주요 최적화 내용

### 1. Pydantic AI 기반 의도 분석 (preprocessor.py)
- **문제**: 사용자의 구어체 질문에서 핵심 법률 키워드를 추출하지 못해 일반적인 답변이 나가는 경우가 많았음.
- **해결**: `preprocessor.py`에서 `LegalIntent` 객체를 생성하여 카테고리(Category), 사실관계(Factual Summary), 핵심 키워드(Legal Keywords)를 강제로 추출하도록 함.
- **결과**: 검색 쿼리가 훨씬 정제되어 정확한 법령이 리트리브될 확률이 높아짐.

### 2. Lockdown 전략 (rag.py - LegalScorer)
- **문제**: '부동산' 질문을 하다가 갑자기 '형법' 관련 키워드가 섞일 경우 이전 검색 결과가 오염되는 현상.
- **해결**: 
    - **Negative Scoring**: 사용자의 현재 질문 카테고리와 다른 법령이 검색될 경우 점수에 0.8배 페널티를 부여.
    - **Category Boosting**: 질문의 성격이 특정 카테고리에 강하게 부합할 경우 0.35점의 보너스 점수를 부여.
- **결과**: 다른 도메인의 간섭을 최소화하고 현재 주제에 집중된 검색 결과를 유지.

### 3. 모듈화 및 파이프라인 정돈 (app.py, rag.py)
- **효과**: `rag.py`를 `Retriever`와 `Scorer`로 분리하여 각 부품을 독립적으로 테스트할 수 있게 됨. `app.py`는 SSE 통신 규약을 유지하면서도 내부 파이프라인이 깔끔하게 정리됨.

## 🚀 향후 과제
- 리랭커(`BAAI/bge-reranker-v2-m3`)의 임계값(Threshold)을 데이터셋에 맞춰 미세 조정하여 불필요한 노이즈 제거 예정.
