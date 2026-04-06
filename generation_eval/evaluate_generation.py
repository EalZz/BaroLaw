import json
import re
from typing import List, Dict, Any

class GenerationEvaluator:
    def __init__(self):
        # 나이브 가치 측정을 위한 전문 용어 리스트 (샘플)
        self.legal_jargon = [
            "주거침입", "절도", "기망", "불법영득의사", "미필적 고의", 
            "위법성", "조각사유", "부작위", "기수", "미수"
        ]

    def evaluate_simplicity(self, body_text: str) -> float:
        """
        나이브 가치 평가: 본문 내 법률 전문 용어의 밀도를 측정합니다.
        밀도가 낮을수록(일상어가 많을수록) 높은 점수 부여.
        """
        if not body_text: return 0.0
        words = body_text.split()
        jargon_count = sum(1 for word in words if any(j in word for j in self.legal_jargon))
        
        # 간단한 밀도 역산 점수 (0~100)
        density = (jargon_count / len(words)) if words else 0
        score = max(0.0, 100.0 - (density * 500.0)) # 가중치 500
        return float(round(score, 2))

    def evaluate_format_and_tags(self, full_text: str, basis_text: str, details_text: str) -> Dict[str, Any]:
        """
        포맷 무결성 평가: 태그의 존재 유무와 JSON 데이터의 유효성을 검증합니다.
        """
        has_basis = "---[LEGAL_BASIS]---" in full_text
        has_details = "---[LEGAL_DETAILS]---" in full_text
        
        json_valid = False
        if details_text:
            try:
                data = json.loads(details_text)
                if isinstance(data, list) and len(data) > 0:
                    json_valid = True
            except json.JSONDecodeError:
                json_valid = False
                
        return {
            "tags_found": has_basis and has_details,
            "json_integrity": json_valid,
            "score": 100 if (has_basis and has_details and json_valid) else 0
        }

    def evaluate_all(self, result_obj: Dict[str, Any]) -> Dict[str, Any]:
        """종합 평가 결과 생성"""
        simplicity_score = self.evaluate_simplicity(result_obj.get("body", ""))
        format_res = self.evaluate_format_and_tags(
            result_obj.get("raw_content", ""),
            result_obj.get("basis", ""),
            result_obj.get("details", "")
        )
        
        return {
            "model": result_obj.get("model"),
            "simplicity_score": simplicity_score,
            "format_integrity": format_res["score"],
            "total_score": float(round((simplicity_score + format_res["score"]) / 2.0, 2))
        }
