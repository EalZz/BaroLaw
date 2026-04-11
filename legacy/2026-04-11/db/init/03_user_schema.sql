-- ================================================================
-- 03_user_schema.sql
-- User Service DB (voice_db): 프로필, 세션, 대화 이력 테이블 스키마 정의.
-- 로그인 기능 추가 시 account_id만 연결하면 멀티 디바이스 동기화가 가능하도록 설계.
-- ================================================================

\c user_db;

-- ------------------------------------------------------------------
-- 1. 사용자 프로필 테이블 (profiles)
--    로그인 없이도 기기 UID(device_uid)로 동작하며,
--    나중에 account_id(이메일/소셜)를 연결하여 멀티 디바이스 지원.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profiles (
    profile_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_uid      VARCHAR(255) UNIQUE NOT NULL,  -- 기기 고유 ID (현재 식별자)
    account_id      VARCHAR(255) UNIQUE,            -- 로그인 계정 ID (초기 NULL)
    display_name    VARCHAR(100),                  -- 표시 이름 (향후 사용)
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS profiles_device_uid_idx ON profiles (device_uid);
CREATE INDEX IF NOT EXISTS profiles_account_id_idx ON profiles (account_id);

-- ------------------------------------------------------------------
-- 2. 대화 세션 테이블 (sessions)
--    1 profile : N sessions 관계.
--    첫 번째 질문 기반으로 제목이 자동 생성됨 (앱 로직에서 처리).
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    session_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id  UUID NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    title       VARCHAR(200) DEFAULT '새 대화',   -- 첫 질문 기반 자동 생성
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sessions_profile_id_idx ON sessions (profile_id);
CREATE INDEX IF NOT EXISTS sessions_updated_at_idx ON sessions (updated_at DESC);

-- ------------------------------------------------------------------
-- 3. 대화 이력 테이블 (chat_history)
--    1 session : N messages 관계.
--    role = 'user' | 'ai' 로 메시지를 구분 (한 행 = 한 메시지).
--    referenced_id로 AI가 참조한 법령/QA의 knowledge_db ID를 기록.
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_history (
    msg_id          BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL CHECK (role IN ('user', 'ai')),
    content         TEXT NOT NULL,
    referenced_type VARCHAR(20),                   -- 'STATUTE' | 'OFFICIAL_GUIDE' | NULL
    referenced_id   INTEGER,                       -- knowledge_db의 레코드 ID
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_history_session_id_idx ON chat_history (session_id);
CREATE INDEX IF NOT EXISTS chat_history_created_at_idx ON chat_history (session_id, created_at ASC);

-- ------------------------------------------------------------------
-- 세션 업데이트 시간 자동 갱신 트리거
-- ------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_session_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE sessions SET updated_at = NOW()
    WHERE session_id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trigger_update_session_on_chat
    AFTER INSERT ON chat_history
    FOR EACH ROW
    EXECUTE FUNCTION update_session_timestamp();
