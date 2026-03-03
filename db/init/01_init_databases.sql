-- ================================================================
-- 01_init_databases.sql
-- Docker 컨테이너 최초 기동 시 자동 실행되는 초기화 스크립트.
-- knowledge_db 생성 및 양쪽 DB에 pgvector 익스텐션을 활성화한다.
-- ================================================================

-- 1. Knowledge DB 생성 (User DB인 voice_db는 환경변수로 이미 생성됨)
CREATE DATABASE knowledge_db;

-- 2. user_db에 pgvector 익스텐션 활성화
\c user_db;
CREATE EXTENSION IF NOT EXISTS vector;

-- 3. knowledge_db에 pgvector 익스텐션 활성화
\c knowledge_db;
CREATE EXTENSION IF NOT EXISTS vector;
