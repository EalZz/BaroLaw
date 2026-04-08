from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class LegalCategory(str, Enum):
    CRIMINAL = "CRIMINAL"   # 형사 (폭행, 절도 등)
    FRAUD = "FRAUD"         # 사기 (보이스피싱, 중고차 사기 등)
    CIVIL = "CIVIL"         # 민사 (손해배상, 대여금 등)
    TRAFFIC = "TRAFFIC"     # 교통 (음주운전, 사고 등)
    LABOR = "LABOR"         # 노동 (임금체불, 부당해고 등)
    REAL_ESTATE = "REAL_ESTATE" # 주거/부동산 (전세사기, 임대차 등)
    UNCERTAIN = "UNCERTAIN" # 불확실 (추가 질문 필요)

class LegalIntent(BaseModel):
    """사용자의 질문에서 법률적 의도와 핵심 정보를 추출합니다."""
    
    category: LegalCategory = Field(
        description="가장 적합한 법률 카테고리. 판단이 어려우면 UNCERTAIN 선택."
    )
    
    legal_keywords: List[str] = Field(
        description="RAG 검색에 사용할 핵심 법률 용어 (예: 절도죄, 기망행위, 임대차계약)."
    )
    
    factual_summary: str = Field(
        description="사용자가 주장하는 핵심 사실관계의 짧은 요약 (구어체 제거)."
    )
    
    entities: List[str] = Field(
        default_factory=list,
        description="언급된 인물이나 사물 (예: 가해자, 집주인, 중고차, 근로계약서)."
    )
    
    is_multiturn_continuation: bool = Field(
        description="이전 대화 맥락을 잇는 질문인지 여부."
    )
    
    missing_info_request: Optional[str] = Field(
        default=None, 
        description="카테고리 판별이나 법률 진단을 위해 사용자에게 추가로 물어봐야 할 내용."
    )
