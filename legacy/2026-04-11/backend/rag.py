import os
import json
import torch
import logging
import yaml
import re
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Set
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

def load_rag_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

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
        
    def build(self, 
              corpus: List[Dict[str, Any]], 
              rerank_results: List[Tuple[int, float]], 
              category_law_boost: Dict[str, Dict[str, float]], 
              category: str = None, 
              candidate_categories: List[str] = None, 
              legal_keywords: List[str] = None, 
              shield_config: Dict[str, Any] = None, 
              injected_ids: Set[int] = None) -> List[Dict[str, Any]]:
        injected_ids = injected_ids or set()
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
            
            boost_score = 0.0
            search_cats = candidate_categories if candidate_categories else ([category] if category else [])
            for cat in search_cats:
                if cat in category_law_boost:
                    target_boosts = category_law_boost[cat]
                    boost_val = target_boosts.get(full_law_name) 
                    if boost_val is None:
                        boost_val = target_boosts.get(base_law_name, 0.0)
                    boost_score += boost_val

            # [v9.0 Phase 2.8.1] Exclusive Penalty & Traffic Correction
            if shield_config and legal_keywords:
                # 동물학대 시 형법 제273조 페널티
                if any(any(x in k for x in ["동물", "강아지", "고양이", "반려"]) for k in legal_keywords):
                    if "형법" in full_law_name and ("제273조" in full_law_name or "학대" in full_law_name):
                        boost_score -= 5.0 # 동물보호법 1위 보장 위해 강화

                # 미세 교통 위반 시 특가법 페널티 (도로교통법 정답 보호)
                if category == "TRAFFIC" or any("TRAFFIC" == c for c in (candidate_categories or [])):
                    critical_traffic = ["치사", "도주", "음주운전", "어린이보호구역", "위험운전"]
                    if not any(any(c in k for c in critical_traffic) for k in legal_keywords):
                        if "특정범죄 가중처벌" in full_law_name:
                            boost_score -= 2.5 # 단순 법규 위반 시 특가법을 하단으로 밀어냄

            # [v9.0 Phase 2.8.1] Sniper Anchoring Mega-Boost
            if idx in injected_ids:
                boost_score += 50.0 
                logger.info(f"[Sniper] Mega-Boost applied to: {full_law_name}")

            final_score = rerank_score + boost_score
            
            # Strong Linkage Boost
            if shield_config and legal_keywords:
                strong_laws = shield_config.get('strong_linkage_laws', [])
                for target_law in strong_laws:
                    if target_law in full_law_name:
                        if any(target_law in kw for kw in legal_keywords):
                            final_score += 1.5 
                        else:
                            final_score += 0.5

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
        self.category_law_boost = config.get('category_boost', {})
        self.domain_shield_config = config.get('refinement', {}).get('domain_shield', {})
        self.baseline_injection = config.get('refinement', {}).get('baseline_injection', {})
        self.triggered_injection = config.get('refinement', {}).get('triggered_injection', [])
        self.legal_synonyms = config.get('refinement', {}).get('legal_synonyms', {})
        self.domain_crossover = config.get('refinement', {}).get('domain_crossover', {})
        self.initialized = True

    def search(self, query: str, category: str = None, original_query: str = None, candidate_categories: List[str] = None, legal_keywords: List[str] = None) -> Dict[str, Any]:
        if not self.initialized: self.initialize()
        def _get_statutes(q, cats, keywords, injection_targets=None, triggered_injection=None):
            injected_ids = set()
            bm25_res = self.bm25_retriever.search(q)
            vector_res = self.vector_retriever.search(q)
            fused_indices = self.rrf_fusion.fuse(bm25_res, vector_res)
            
            # Baseline Sniper Tow-in
            if injection_targets:
                for target in injection_targets:
                    clean_target = target.replace(" ", "")
                    for idx, item in enumerate(self.corpus):
                        corpus_str = f"{str(item.get('metadata', {}).get('law_name'))}{str(item.get('metadata', {}).get('article'))}".replace(" ", "")
                        if clean_target in corpus_str:
                            if idx in fused_indices: fused_indices.remove(idx)
                            fused_indices.insert(0, idx)
                            injected_ids.add(idx)
                            break

            # [v9.0 Phase 2.8.2] Triggered Sniper Tow-in: 리스트 완전 순회 및 강제 견인 (Fixed Mapping)
            if triggered_injection and isinstance(triggered_injection, list) and keywords:
                for conf in triggered_injection:
                    target_cat = conf.get("category")
                    if any(target_cat == c for c in cats) if cats else (target_cat == category):
                        trigger_kws = conf.get("keywords", [])
                        if any(any(tk in k for tk in trigger_kws) for k in keywords):
                            inject_list = conf.get("inject", [])
                            for target in inject_list:
                                clean_target = target.replace(" ", "")
                                for idx, item in enumerate(self.corpus):
                                    corpus_str = f"{str(item.get('metadata', {}).get('law_name'))}{str(item.get('metadata', {}).get('article'))}".replace(" ", "")
                                    if clean_target in corpus_str:
                                        # 이미 있으면 삭제 후 0번(최상단)으로 이동 (리랭커 노출 보장)
                                        if idx in fused_indices: fused_indices.remove(idx)
                                        fused_indices.insert(0, idx)
                                        injected_ids.add(idx)
                                        logger.info(f"[Tow-in] Success: {target}")
                                        break

            reranked_res = self.reranker.rerank(q, self.corpus, fused_indices)
            return self.context_builder.build(self.corpus, reranked_res, self.category_law_boost, category, cats, keywords, self.domain_shield_config, injected_ids)

        search_query = query
        if category == "FRAUD": search_query += " 기망 편취 재산상 이익"
            
        inj_targets = self.baseline_injection.get(category, []) if category else []
        final_kws = [self.legal_synonyms.get(kw, kw) for kw in (legal_keywords or [])]
        trig_map = self.triggered_injection
        
        statutes = _get_statutes(search_query, candidate_categories, final_kws, inj_targets, trig_map)
        return {"statutes": statutes}

def search_relevant_context(query, original_query=None, turn_count=1, llm_keywords=None, session_category=None, prev_statute_names=None):
    try:
        pipeline = LegalRAGPipeline()
        search_query = query
        candidates = [session_category] if session_category else []
        if llm_keywords:
            expanded = []
            for kw in llm_keywords:
                expanded.append(pipeline.legal_synonyms.get(kw, kw))
                for trigger, domains in pipeline.domain_crossover.items():
                    if trigger in kw: candidates.extend(domains)
            final_keywords = list(dict.fromkeys(expanded))
            if final_keywords: search_query += f" {' '.join(final_keywords)}"
        
        if turn_count > 1 and prev_statute_names:
            search_query += f" {' '.join(prev_statute_names)}"
            
        return pipeline.search(search_query, category=session_category, original_query=original_query or query, candidate_categories=list(dict.fromkeys(candidates)), legal_keywords=llm_keywords)
    except Exception as e:
        logger.error(f"Search Error: {str(e)}")
        return {"statutes": []}

def build_rag_context(results):
    statutes = results.get("statutes", [])
    if not statutes: return "관련 법령을 찾을 수 없습니다."
    ctx = "[관련 법령 정보]\n"
    for i, s in enumerate(statutes):
        ctx += f"{i+1}. {s['law_name']} ({s['article']}): {s['content']}\n"
    return ctx

def get_first_referenced_id(results):
    statutes = results.get("statutes", [])
    if statutes: return statutes[0].get("id"), "statute"
    return None, None

def get_model():
    p = LegalRAGPipeline()
    p.initialize()
    return p

def get_reranker():
    p = LegalRAGPipeline()
    p.initialize()
    return p.reranker
