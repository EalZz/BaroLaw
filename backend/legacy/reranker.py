from langchain.retrievers.document_compressors.base import BaseDocumentCompressor
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from typing import Sequence
import pydantic

class CrossEncoderReranker(BaseDocumentCompressor):
    """
    HuggingFace의 CrossEncoder 모델을 활용하여 초기 검색된 문서들의 순위를 
    사용자 질의(Query) 문맥에 맞게 재정렬(Re-ranking)하는 LangChain 호환 컴프레서입니다.
    """
    model: CrossEncoder
    top_n: int = 3

    class Config:
        # Pydantic이 CrossEncoder 클래스 타입 검사를 통과시키도록 허용
        arbitrary_types_allowed = True

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks=None,
    ) -> Sequence[Document]:
        if not documents:
            return []
        
        # 크로스 인코더는 [질문, 문서내용] 형태의 쌍(Pair) 기반 입력을 받습니다.
        model_inputs = [[query, doc.page_content] for doc in documents]
        
        # 언어 모델 연산을 통해 0~1 사이의 연관성 점수를 일괄 예측합니다.
        scores = self.model.predict(model_inputs)
        
        # 문서와 점수를 짝채우고 점수(score) 내림차순으로 정렬합니다.
        doc_score_pairs = list(zip(documents, scores))
        doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # 지정된 갯수(top_n) 만큼 최상위 문서를 반환합니다.
        return [doc for doc, score in doc_score_pairs[:self.top_n]]
