import os
from datetime import datetime
import pytz
from uuid import uuid4

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, create_engine, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pgvector.sqlalchemy import Vector

# 1. Database URLs (Docker 환경 변수 기반)
# 로컬 테스트 환경을 위해 'db' 호스트가 안 보이면 'localhost'로 자동 전환
DEFAULT_USER_URL = "postgresql://user:password@db:5432/user_db"
DEFAULT_KNOWLEDGE_URL = "postgresql://user:password@db:5432/knowledge_db"

USER_DB_URL = os.getenv("DATABASE_URL", DEFAULT_USER_URL)
KNOWLEDGE_DB_URL = os.getenv("KNOWLEDGE_DB_URL", DEFAULT_KNOWLEDGE_URL)

# WSL/Host 환경에서 실행 시 'db' 호스트명을 'localhost'로 변환 (테스트 용)
if not os.getenv("DATABASE_URL") and not os.path.exists("/.dockerenv"):
    USER_DB_URL = USER_DB_URL.replace("@db:", "@localhost:")
    KNOWLEDGE_DB_URL = KNOWLEDGE_DB_URL.replace("@db:", "@localhost:")

# 2. Engines & Session Factory
user_engine = create_engine(USER_DB_URL)
knowledge_engine = create_engine(KNOWLEDGE_DB_URL)

SessionUser = sessionmaker(autocommit=False, autoflush=False, bind=user_engine)
SessionKnowledge = sessionmaker(autocommit=False, autoflush=False, bind=knowledge_engine)

Base = declarative_base()

# ==========================================
# [User Service DB Models - user_db]
# ==========================================

class Profile(Base):
    """사용자 프로필 (비로그인 UID 기반에서 로그인 계정으로 확장 가능)"""
    __tablename__ = "profiles"

    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_uid = Column(String(255), unique=True, nullable=False, index=True)
    account_id = Column(String(255), unique=True, nullable=True, index=True)
    display_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sessions = relationship("ChatSession", back_populates="profile", cascade="all, delete-orphan")

class ChatSession(Base):
    """대화 세션 (ChatGPT 스타일 대화방)"""
    __tablename__ = "sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), default="새 대화")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile = relationship("Profile", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """개별 메시지 이력 (한 행 = 한 메시지)"""
    __tablename__ = "chat_history"

    msg_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(10), nullable=False) # 'user' or 'ai'
    content = Column(Text, nullable=False)
    referenced_type = Column(String(20), nullable=True) # 'STATUTE' or 'OFFICIAL_GUIDE'
    referenced_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

# ==========================================
# [Knowledge DB Models - knowledge_db]
# ==========================================

class Statute(Base):
    """법령 조문 데이터 (pgvector 지원)"""
    __tablename__ = "statutes"
    __bind_key__ = 'knowledge' # 다중 DB 관리 구분용

    id = Column(Integer, primary_key=True)
    topic = Column(String(50), nullable=False)
    law_name = Column(Text, nullable=False)
    article = Column(Text)
    content = Column(Text, nullable=False)
    source_type = Column(String(20), default="STATUTE")
    embedding = Column(Vector(768)) # pgvector 전용 타입
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OfficialQA(Base):
    """생활법률 Q&A 데이터 (pgvector 지원)"""
    __tablename__ = "official_qa"
    __bind_key__ = 'knowledge'

    id = Column(Integer, primary_key=True)
    topic = Column(String(50), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source_url = Column(Text)
    source_type = Column(String(30), default="OFFICIAL_GUIDE")
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ==========================================
# [Helper Functions]
# ==========================================

def get_user_db():
    """FastAPI 종속성 주입용 - User DB 세션"""
    db = SessionUser()
    try:
        yield db
    finally:
        db.close()

def get_knowledge_db():
    """지식 검색용 - Knowledge DB 세션"""
    db = SessionKnowledge()
    try:
        yield db
    finally:
        db.close()

# ------------------------------------------
# 핵심 비즈니스 로직 함수들
# ------------------------------------------

def get_or_create_profile(db: Session, device_uid: str) -> Profile:
    """기기 ID로 프로필 조회 및 없을 시 생성"""
    profile = db.query(Profile).filter(Profile.device_uid == device_uid).first()
    if not profile:
        profile = Profile(device_uid=device_uid)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

def create_chat_session(db: Session, profile_id: str, first_query: str = None, session_id: str = None) -> ChatSession:
    """새로운 대화 세션 생성"""
    title = (first_query[:30] + '...') if first_query and len(first_query) > 30 else (first_query or "새 대화")
    
    session_data = {"profile_id": profile_id, "title": title}
    if session_id:
        session_data["session_id"] = session_id
        
    new_session = ChatSession(**session_data)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

def save_chat_message(db: Session, session_id: str, role: str, content: str, ref_type: str = None, ref_id: int = None):
    """대화 메시지 저장 및 세션의 updated_at 갱신"""
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        referenced_type=ref_type,
        referenced_id=ref_id
    )
    db.add(msg)
    
    # 세션의 updated_at을 현재 시간으로 강제 업데이트 (목록 정렬을 위함)
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if session:
        session.updated_at = func.now()
        
    db.commit()
    db.refresh(msg)
    return msg

def get_session_history(db: Session, session_id: str, limit: int = 50):
    """특정 세션의 대화 이력 조회 (시간 순)"""
    return db.query(ChatMessage)\
             .filter(ChatMessage.session_id == session_id)\
             .order_by(ChatMessage.created_at.asc())\
             .limit(limit).all()

def get_user_sessions(db: Session, device_uid: str):
    """사용자의 모든 이전 대화 세션 목록 조회"""
    profile = db.query(Profile).filter(Profile.device_uid == device_uid).first()
    if not profile:
        return []
    return db.query(ChatSession)\
             .filter(ChatSession.profile_id == profile.profile_id)\
             .order_by(ChatSession.updated_at.desc()).all()

def delete_chat_session(db: Session, session_id: str):
    """특정 세션 삭제 (연관된 대화 내용도 CASCADE로 자동 삭제됨)"""
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if session:
        db.delete(session)
        db.commit()
        return True
    return False

# 테이블 자동 생성 (없을 경우 새로 만듦)
Base.metadata.create_all(bind=user_engine)
# Base.metadata.create_all(bind=knowledge_engine) # knowledge_db는 pgvector나 별도 스크립트로 초기화하는 것이 일반적임.