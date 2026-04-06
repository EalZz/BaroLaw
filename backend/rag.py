import os
import json
import torch
import logging
import yaml
import re
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder
from kiwipiepy import Kiwi

# 로깅
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BaroLaw-RAG-Hybrid")

# 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "autorag_data")
CORPUS_PATH = os.path.join(DATA_DIR, "corpus.parquet")
CACHE_PATH = os.path.join(DATA_DIR, "corpus_embeddings.pt")
CONFIG_PATH = os.path.join(BASE_DIR, "rag_config.yaml")

# ------------------------------------------------------------
# 0. Domain Boost Config
# ------------------------------------------------------------ㅛ
# ------------------------------------------------------------
# [v8.53 Stable - Dynamic Loading]
# Note: LEGAL_SYNONYMS, DOMAIN_CROSSOVER_MAP are now loaded from rag_config.yaml


# ------------------------------------------------------------
# 1. Config Loader
# ------------------------------------------------------------
def load_rag_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

# ------------------------------------------------------------
# 2. Components
# ------------------------------------------------------------

class QueryPreprocessor:
    def __init__(self):
        self.kiwi = Kiwi()
        self.target_tags = ('NNG', 'NNP', 'VV', 'VA', 'XR')
        self.stopwords = {'제', '조', '항', '호', '및', '등', '경우', '사항', '기준', '방법', '내용', '확인'}
        
    def tokenize(self, text: str) -> List[str]:
        if not text: return []
        tokens = self.kiwi.tokenize(text)
        return [t.form for t in tokens if t.tag in self.target_tags and t.form not in self.stopwords]

class BM25Retriever:
    def __init__(self, corpus: List[Dict], preprocessor: QueryPreprocessor, top_k: int):
        self.preprocessor = preprocessor
        self.top_k = top_k
        self.corpus = corpus
        logger.info(f"[BM25] Indexing {len(corpus)} records...")
        self.corpus_tokens = [
            self.preprocessor.tokenize(f"{str(item.get('metadata', {}).get('law_name') or '')} {str(item.get('contents') or '')}") 
            for item in corpus
        ]
        self.bm25 = BM25Okapi(self.corpus_tokens)
        
    def search(self, query: str) -> List[Tuple[int, float]]:
        query_tokens = self.preprocessor.tokenize(query)
        if not query_tokens: return []
        scores = self.bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[::-1][:self.top_k]
        return [(int(idx), float(scores[idx])) for idx in top_indices]

class VectorRetriever:
    def __init__(self, corpus: List[Dict], top_k: int):
        self.corpus = corpus
        self.top_k = top_k
        device = "cpu"
        self.model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=device)
        if os.path.exists(CACHE_PATH):
            self.embeddings = torch.load(CACHE_PATH, map_location="cpu")
        else:
            texts = [str(item.get('contents') or '') for item in self.corpus]
            self.embeddings = self.model.encode(texts, convert_to_tensor=True)
            torch.save(self.embeddings.cpu(), CACHE_PATH)

    def search(self, query: str) -> List[Tuple[int, float]]:
        query_emb = self.model.encode(query, convert_to_tensor=True)
        cos_scores = torch.nn.functional.cosine_similarity(query_emb, self.embeddings).cpu().numpy()
        top_indices = np.argsort(cos_scores)[::-1][:self.top_k]
        return [(int(idx), float(cos_scores[idx])) for idx in top_indices]

class Reranker:
    def __init__(self, model_name: str, top_k: int):
        self.top_k = top_k
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CrossEncoder(model_name, device=device)
        
    def rerank(self, query: str, corpus: List[Dict], indices: List[int]) -> List[Tuple[int, float]]:
        if not indices: return []
        target_indices = indices[:self.top_k]
        pairs = [[query, f"{str(corpus[idx].get('metadata', {}).get('law_name') or '')} {str(corpus[idx].get('contents') or '')}"] for idx in target_indices]
        scores = self.model.predict(pairs, batch_size=8)
        return [(int(idx), float(score)) for idx, score in zip(target_indices, scores)]

class HybridRRF:
    def __init__(self, weight: float, top_k: int):
        self.weight = weight
        self.top_k = top_k
        
    def fuse(self, bm25_results: List[Tuple[int, float]], vector_results: List[Tuple[int, float]]) -> List[int]:
        rrf_scores = defaultdict(float)
        for rank, (idx, _) in enumerate(bm25_results, 1):
            rrf_scores[idx] += 1.0 / (rank ** self.weight)
        for rank, (idx, _) in enumerate(vector_results, 1):
            rrf_scores[idx] += 1.0 / (rank ** self.weight)
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in ranked[:self.top_k]]

class ContextBuilder:
    def __init__(self, max_results: int):
        self.max_results = max_results
        
    def build(self, corpus: List[Dict], rerank_results: List[Tuple[int, float]], category_law_boost: Dict[str, Any], category: str = None, candidate_categories: List[str] = None) -> List[Dict]:
        all_results = []
        seen = set()
        for idx, rerank_score in rerank_results:
            item = corpus[idx]
            meta = item.get('metadata', {})
            full_law_name = str(meta.get('law_name') or "")
            base_law_name = full_law_name.split(" 제")[0].split("(")[0].strip()
            key = f"{full_law_name}_{str(meta.get('article') or '')}"
            if key in seen: continue
            seen.add(key)
            
            # [v8.1] 하이브리드 부스팅: 후보 도메인 중 하나라도 매칭되면 가중치 부여
            boost_score = 0.0
            search_cats = candidate_categories if candidate_categories else ([category] if category else [])
            for cat in search_cats:
                if cat in category_law_boost:
                    cat_boost = category_law_boost[cat].get(base_law_name, 0.0)
                    boost_score = max(boost_score, cat_boost)
            
            final_score = rerank_score + boost_score
            
            # [v8.65] Strong Linkage Boost: 전처리기 키워드와 법령명이 직접 매칭될 경우 추가 가중치
            if candidate_categories: # 리스트 형태일 때 (진단 등)
                keywords = [] 
            else: # 일반 검색 시 keywords는 상위 레벨에서 관리됨 (필요시 파라미터 확장 가능)
                # 여기서는 law_name 자체가 키워드로 들어오는 경우를 대비
                pass

            all_results.append({
                "id": item.get('doc_id'),
                "law_name": full_law_name,
                "article": str(meta.get('article') or ""),
                "content": str(item.get('contents') or ""),
                "metadata": meta,
                "source": str(meta.get('source', '')),
                "_rerank_score": rerank_score,
                "_boost_score": boost_score,
                "_final_score": final_score
            })
        all_results.sort(key=lambda x: x["_final_score"], reverse=True)
        statutes = [r for r in all_results if r.get('source') == 'statutes']
        qa = [r for r in all_results if r.get('source') != 'statutes']
        s_count = int(self.max_results * 0.7)
        q_count = self.max_results - s_count
        results = statutes[:s_count] + qa[:q_count]
        return results[:self.max_results]

# ------------------------------------------------------------
# 3. Main Pipeline
# ------------------------------------------------------------

class LegalRAGPipeline:
    _instance = None
    initialized: bool

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LegalRAGPipeline, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def initialize(self):
        if self.initialized: return
        config = load_rag_config()
        scoring = config.get('scoring', {}).get('weights', {})
        limits = config.get('limits', {})
        rrf_weight = float(scoring.get('rrf_weight', 3.0))
        retrieval_k = int(scoring.get('retrieval_top_k', 50))
        top_statutes = int(limits.get('top_statutes', 10))
        reranker_name = config.get('models', {}).get('reranker', "BAAI/bge-reranker-v2-m3")
        
        df = pd.read_parquet(CORPUS_PATH)
        self.corpus = df.to_dict('records')
        self.preprocessor = QueryPreprocessor()
        self.bm25_retriever = BM25Retriever(self.corpus, self.preprocessor, top_k=retrieval_k)
        self.vector_retriever = VectorRetriever(self.corpus, top_k=retrieval_k)
        self.rrf_fusion = HybridRRF(weight=rrf_weight, top_k=retrieval_k * 2) 
        self.reranker = Reranker(model_name=reranker_name, top_k=30)
        self.context_builder = ContextBuilder(max_results=top_statutes)
        refinement = config.get('refinement', {})
        self.legal_synonyms = refinement.get('legal_synonyms', {})
        self.domain_crossover = refinement.get('domain_crossover', {})
        self.category_law_boost = config.get('category_boost', {})
        self.initialized = True

    def search(self, query: str, category: str = None, original_query: str = None, candidate_categories: List[str] = None, legal_keywords: List[str] = None) -> Dict[str, Any]:
        if not self.initialized: self.initialize()
        def _get_statutes(q, cats, keywords):
            bm25_res = self.bm25_retriever.search(q)
            vector_res = self.vector_retriever.search(q)
            fused_indices = self.rrf_fusion.fuse(bm25_res, vector_res)
            reranked_res = self.reranker.rerank(q, self.corpus, fused_indices)
            return self.context_builder.build(self.corpus, reranked_res, self.category_law_boost, category, cats)

        # [v8.53 Fix] LLM 키워드가 포함된 쿼리를 우선 사용하도록 수정
        search_query = query
        
        # 키워드 보정 (약칭 -> 정석 명칭)
        final_keywords = []
        if legal_keywords:
            for kw in legal_keywords:
                final_keywords.append(self.legal_synonyms.get(kw, kw))
        
        statutes = _get_statutes(search_query, candidate_categories, final_keywords)
        if (not statutes or len(statutes) < 2) and original_query and original_query != query:
            statutes = _get_statutes(original_query, candidate_categories, final_keywords)
        return {"statutes": statutes}

def search_relevant_context(
    query: str,
    original_query: str = None,
    turn_count: int = 1,
    llm_keywords: List[str] = None,
    session_category: str = None,
    prev_statute_names: List[str] = None
) -> Dict[str, Any]:
    try:
        pipeline = LegalRAGPipeline()
        search_query = query
        
        # [v8.1] 교차 도메인 타겟팅 로직
        candidates = [session_category] if session_category else []
        if llm_keywords:
            expanded_keywords = []
            for kw in llm_keywords:
                # 약칭 확장
                if kw in pipeline.legal_synonyms:
                    expanded_keywords.append(pipeline.legal_synonyms[kw])
                
                # 교차 도메인 후보군 추출
                for trigger, domains in pipeline.domain_crossover.items():
                    if trigger in kw:
                        candidates.extend(domains)
                
                if len(kw) > 1 and not re.match(r'^(법률|조약|특별법)$', kw):
                    expanded_keywords.append(kw)
            
            # 중복 제거
            final_keywords = list(dict.fromkeys(expanded_keywords))
            if final_keywords:
                search_query += f" {' '.join(final_keywords)}"
            
        candidate_categories = list(dict.fromkeys(candidates))
            
        if turn_count > 1 and prev_statute_names:
            search_query += f" {' '.join(prev_statute_names)}"
            
        return pipeline.search(
            search_query, 
            category=session_category, 
            original_query=original_query or query,
            candidate_categories=candidate_categories,
            legal_keywords=llm_keywords
        )
    except Exception as e:
        logger.error(f"Search Error: {str(e)}")
        return {"statutes": [], "keywords": [], "qa": []}

def build_rag_context(rag_results: Dict[str, Any]) -> str:
    statutes = rag_results.get("statutes", [])
    if not statutes: return "관련 법령을 찾을 수 없습니다."
    ctx = "[관련 법령 정보]\n"
    for i, s in enumerate(statutes):
        ctx += f"{i+1}. {s['law_name']} ({s['article']}): {s['content']}\n"
    return ctx

def get_first_referenced_id(rag_results: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    statutes = rag_results.get("statutes", [])
    if statutes: return statutes[0].get("id"), "statute"
    return None, None

def get_model():
    p = LegalRAGPipeline()
    if not p.initialized: p.initialize()
    return p.vector_retriever.model

def get_reranker():
    p = LegalRAGPipeline()
    if not p.initialized: p.initialize()
    return p.reranker.model
