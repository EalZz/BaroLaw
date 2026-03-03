-- ================================================================
-- 02_knowledge_schema.sql
-- Knowledge DB: 법령 조문 및 공식 Q&A 테이블 스키마 정의.
-- pgvector의 벡터 컬럼(embedding)을 포함하여 Semantic Search를 지원한다.
-- ================================================================

\c knowledge_db;

-- ------------------------------------------------------------------
-- 1. 법령 조문 테이블 (statutes)
--    법령정보센터 원문을 조항 단위로 분절하여 저장.
--    source_type = 'STATUTE' 고정.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS statutes (
    id          SERIAL PRIMARY KEY,
    topic       VARCHAR(50) NOT NULL,           -- 'traffic','estate','fraud','criminal'
    law_name    TEXT NOT NULL,                  -- 법령명 (예: 도로교통법)
    article     TEXT,                           -- 조항 번호 (예: 제44조제1항)
    content     TEXT NOT NULL,                  -- 조문 본문
    source_type VARCHAR(20) DEFAULT 'STATUTE',
    embedding   vector(768),                    -- ko-sroberta-multitask 768차원
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 벡터 검색 인덱스 (HNSW: 대용량에서도 빠른 ANN 검색)
CREATE INDEX IF NOT EXISTS statutes_embedding_idx
    ON statutes USING hnsw (embedding vector_cosine_ops);

-- 토픽별 필터링 인덱스
CREATE INDEX IF NOT EXISTS statutes_topic_idx ON statutes (topic);

-- ------------------------------------------------------------------
-- 2. 생활법률 공식 Q&A 테이블 (official_qa)
--    법제처 '찾기 쉬운 생활법률정보' 크롤링 데이터.
--    source_type = 'OFFICIAL_GUIDE' 고정.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS official_qa (
    id          SERIAL PRIMARY KEY,
    topic       VARCHAR(50) NOT NULL,           -- 'traffic','estate','fraud','criminal'
    question    TEXT NOT NULL,                  -- 질문 원문
    answer      TEXT NOT NULL,                  -- 공식 해설 답변
    source_url  TEXT,                           -- 출처 URL (easylaw.go.kr)
    source_type VARCHAR(30) DEFAULT 'OFFICIAL_GUIDE',
    embedding   vector(768),                    -- ko-sroberta-multitask 768차원
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 벡터 검색 인덱스
CREATE INDEX IF NOT EXISTS official_qa_embedding_idx
    ON official_qa USING hnsw (embedding vector_cosine_ops);

-- 토픽별 필터링 인덱스
CREATE INDEX IF NOT EXISTS official_qa_topic_idx ON official_qa (topic);
