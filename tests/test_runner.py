import json
import requests
import uuid
import urllib.parse
import time
import os
import re
from datetime import datetime

# 테스트 설정
BASE_URL = "http://localhost:8000" 
DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
RESULT_DIR = os.path.join(os.path.dirname(__file__), "results")
RESULT_MD = os.path.join(RESULT_DIR, "test_results.md")

# 터미널 출력용 색상
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_MAGENTA = "\033[95m"
COLOR_WHITE = "\033[97m"
COLOR_RESET = "\033[0m"

class TestLogger:
    def __init__(self):
        if not os.path.exists(RESULT_DIR):
            os.makedirs(RESULT_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(RESULT_DIR, f"test_log_v3_{timestamp}.log")
        
    def log(self, message, color=None, flush=False):
        clean_msg = re.sub(r'\033\[[0-9;]*m', '', message)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {clean_msg}\n")
        
        if color:
            print(f"{color}{message}{COLOR_RESET}")
        else:
            print(message)

def stream_chat(user_input, session_id):
    """SSE 스트림에서 텍스트와 메타데이터를 모두 수집합니다."""
    encoded_text = urllib.parse.quote(user_input)
    url = f"{BASE_URL}/chat-stream?text={encoded_text}&uid=test_runner&session_id={session_id}&client_type=app"
    
    full_text = ""
    try:
        with requests.get(url, stream=True, timeout=300) as r:
            if r.status_code != 200:
                return f"ERROR: HTTP {r.status_code}"
                
            for line in r.iter_lines():
                if not line: continue
                decoded_line = line.decode('utf-8').strip()
                if decoded_line.startswith("data: "):
                    content = decoded_line[6:]
                    if content == "[DONE]": break
                    try:
                        data = json.loads(content)
                        msg_chunk = data.get("message", "")
                        full_text += msg_chunk
                    except json.JSONDecodeError:
                        full_text += content
    except Exception as e:
        return f"ERROR: {str(e)}"
    return full_text

def calculate_rag_score(expected_statute, retrieved_text):
    """
    RAG 검색 결과 점수 계산 (1.0 / 0.8 / 0.5)
    """
    if not retrieved_text: return 0.0
    
    # [v9.0 Phase 1] 법령 약칭 동기화 매핑 (v8.53) 및 정식 명칭 매칭 로직 보강
    SYNONYMS = {
        "집합건물법": "집합건물의 소유 및 관리에 관한 법률",
        "특가법": "특정범죄 가중처벌 등에 관한 법률",
        "교특법": "교통사고처리 특례법",
        "주임법": "주택임대차보호법",
        "상임법": "상가건물 임대차보호법",
        "도교법": "도로교통법",
        "정통망법": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
        "학폭법": "학교폭력예방 및 대책에 관한 법률"
    }
    
    # [수정] 조가 없는 경우 (예: "형법", "민법") → law name만 매칭되면 1.0
    if not re.search(r'제?\s*\d+\s*조', expected_statute):
        law_clean = expected_statute.replace(" ", "")
        target_clean = retrieved_text.replace(" ", "")
        for short, full in SYNONYMS.items():
            if short in law_clean: law_clean = full.replace(" ", "")
        if law_clean in target_clean:
            return 1.0
        return 0.0
    
    # 1. 법률명 추출
    law_match = re.match(r'^([가-힣\s]+ 법률?|형법|민법|상법|집합건물법|주택임대차보호법|상가건물 임대차보호법|경범죄 처벌법)', expected_statute)
    law_name = law_match.group(1).strip() if law_match else expected_statute
    
    # 2. 조문 번호 추출
    article_match = re.search(r'제?\s*(\d+)\s*조', expected_statute)
    article_num = article_match.group(1) if article_match else None

    # 가공된 텍스트와 비교
    target_clean = retrieved_text.replace(" ", "")
    law_clean = law_name.replace(" ", "")
    
    # 약칭 치환
    for short, full in SYNONYMS.items():
        if short in law_clean:
            law_clean = full.replace(" ", "")
            break

    # [1.0] Exact Match
    if article_num:
        if (law_clean in target_clean and f"제{article_num}조" in target_clean) or \
           (law_clean in target_clean and f"{article_num}조" in target_clean):
            return 1.0

    # [0.8] Law Match
    if law_clean in target_clean:
        return 0.8

    # [0.5] Ambiguous Match
    keywords = [k for k in re.split(r'[\s,]+', law_name) if len(k) >= 2]
    if any(k in target_clean for k in keywords):
        return 0.5

    return 0.0

def run_tests():
    logger = TestLogger()
    logger.log("🚀 BaroLaw RAG Evaluation System v3.2 (Granular Multi-turn)", COLOR_CYAN)
    
    if not os.path.exists(DATASET_PATH):
        logger.log(f"✘ [Error] {DATASET_PATH} 파일이 없습니다.", COLOR_RED)
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    results = []
    total_turns = 0
    scenarios_passed = 0 
    t1_total = 0
    t1_passed = 0
    cat_match_passed = 0 
    total_final_score = 0.0 # [v7.1] 최종 턴 점수 합계
    error_count = 0 # [v8.53] 에러 발생 횟수
    failed_ids = [] # [v8.53] 실패 케이스 목록
    overall_start_time = time.time() # [v8.53] 전체 시작 시간

    for case in test_cases:
        case_id = case["test_id"]
        desc = case["description"]
        logger.log(f"\n▶ [{case_id}] {desc}")
        
        session_id = str(uuid.uuid4())
        case_info = {"id": case_id, "desc": desc, "turns": []}
        num_turns = len(case["turns"])
        
        for idx, turn in enumerate(case["turns"]):
            total_turns += 1
            t_id = turn["turn_id"]
            user_in = turn["user_input"]
            exp_statutes = turn.get("expected_statutes", [])
            is_t1 = (idx == 0 and num_turns > 1)
            is_last_turn = (idx == num_turns - 1)
            
            logger.log(f"  Turn {t_id}: '{user_in}'", flush=True)
            
            start_time = time.time()
            actual_resp = stream_chat(user_in, session_id)
            elapsed = time.time() - start_time
            
            # [v8.53] 에러 체크
            if actual_resp.startswith("ERROR"):
                error_count += 1
            
            # 파싱
            is_uncertain = "[시스템 안내]\n질문이 다소 모호하여" in actual_resp
            raw_ai_text = actual_resp.split("---[RAG_ENGINE_RESULT]---")[0].split("---[RAG_METADATA]---")[0].strip()
            
            rag_output = ""
            if "---[RAG_ENGINE_RESULT]---" in actual_resp:
                rag_output = actual_resp.split("---[RAG_ENGINE_RESULT]---")[1].split("---[RAG_METADATA]---")[0].strip()
            
            meta_json = "{}"
            if "---[RAG_METADATA]---" in actual_resp:
                meta_json = actual_resp.split("---[RAG_METADATA]---")[1].strip()
            
            try: metadata = json.loads(meta_json)
            except: metadata = {}

            keywords = metadata.get("keywords", [])
            summary = metadata.get("summary", "")
            pred_cat = metadata.get("category", "UNCERTAIN")

            # 스코어 측정
            if not exp_statutes:
                # [v6.9] 기대 법령이 없는 경우: 시스템이 카테고리를 맞췄거나 모호성을 인지(UNCERTAIN)했다면 1.0 부여
                if pred_cat == case["category"] or pred_cat == "UNCERTAIN":
                    best_score = 1.0
                else:
                    best_score = 0.0
            else:
                scores = [calculate_rag_score(s, rag_output) for s in exp_statutes]
                best_score = max(scores) if scores else 0.0
            
            # [v3.7] 카테고리 매칭 로직: 싱글턴 제외 멀티턴 T1(모호한 질문)에서의 UNCERTAIN은 정답임
            is_expected_fallback = (not exp_statutes)
            is_cat_match = (pred_cat == case["category"]) or (is_expected_fallback and pred_cat == "UNCERTAIN")
            
            if is_cat_match: cat_match_passed += 1

            # [v6.7] T1 Policy: 첫 번째 턴(싱글턴 포함)에서의 의도/카테고리 식별 집계
            if idx == 0:
                t1_total += 1
                # 1. 정보를 되묻거나(UNCERTAIN), 2. 최종 카테고리를 미리 맞춘 경우 모두 PASS
                if pred_cat == "UNCERTAIN" or pred_cat == case["category"]:
                    t1_passed += 1

            # 인용 여부
            citation_scores = [calculate_rag_score(s, raw_ai_text) for s in exp_statutes] if exp_statutes else [0.0]
            cite_score = max(citation_scores) if citation_scores else 0.0
            is_yellow = (best_score >= 0.8 and cite_score < 0.5)
            
            # 시나리오 합격 및 점수 누적 (마지막 턴 기준)
            if is_last_turn:
                total_final_score += best_score
                if best_score >= 0.8:
                    scenarios_passed += 1
                else:
                    failed_ids.append(case_id) # [v8.53] 실패 리스트 추가

            # 로그 출력
            cat_mark = "✔" if is_cat_match else "✘"
            # [v3.7] 정당한 Fallback인 경우 마크 변경
            if is_expected_fallback and pred_cat == "UNCERTAIN": cat_mark = "✔ OK"
            
            logger.log(f"    [Category] {pred_cat} ({cat_mark})", COLOR_CYAN if is_cat_match else COLOR_RED)
            kw_str = ', '.join(keywords) if keywords else "비어있음"
            logger.log(f"    [Keywords] {kw_str}", COLOR_MAGENTA)
            if summary:
                logger.log(f"    [Summary] {summary}", COLOR_WHITE)
            if exp_statutes:
                logger.log(f"    [Expected] {exp_statutes[0]}", COLOR_YELLOW)
            if is_uncertain or (pred_cat == "UNCERTAIN"):
                logger.log(f"    [System] Fallback Mode Enabled", COLOR_YELLOW)
            if rag_output:
                logger.log(f"    [Retrieved] {rag_output.replace('|', ', ')}", COLOR_CYAN)
            
            if best_score >= 0.8:
                mark = "✔ PASS" if not is_yellow else "⚠ PASS (No Citation)"
                logger.log(f"    {mark} Sc:{best_score:.1f} ({elapsed:.1f}s)", COLOR_GREEN)
            else:
                # [v5.1] T-Stage Policy: 멀티턴 중간 단계에서 카테고리 적중/폴백 시 FAIL 대신 PASS 처리
                is_correct_fallback = (is_expected_fallback and pred_cat == "UNCERTAIN")
                is_t_stage_pass = (not is_last_turn and (pred_cat == case["category"] or pred_cat == "UNCERTAIN"))
                
                if is_correct_fallback:
                    status_msg = "✔ OK (Fallback)"
                elif is_t_stage_pass:
                    status_msg = f"✔ PASS (T-Stage)"
                else:
                    status_msg = "✘ FAIL"
                
                color = COLOR_GREEN if "PASS" in status_msg or "OK" in status_msg else COLOR_RED
                logger.log(f"    {status_msg} Sc:{best_score:.1f} ({elapsed:.1f}s)", color)

            case_info["turns"].append({
                "turn": t_id, "score": best_score, "is_uncertain": is_uncertain, 
                "is_yellow": is_yellow, "elapsed": elapsed
            })
            
        results.append(case_info)
        logger.log("-" * 50)

    # [v8.53] 전체 소요 시간 계산
    overall_duration = time.time() - overall_start_time
    
    # 최종 리포트 저장
    save_markdown_report_v3_4(results, scenarios_passed, t1_passed, t1_total, cat_match_passed, total_turns, len(test_cases), total_final_score, overall_duration, error_count, failed_ids)
    
    scenario_success = (scenarios_passed / len(test_cases) * 100) if test_cases else 0
    t1_success = (t1_passed / t1_total * 100) if t1_total > 0 else 0
    cat_success = (cat_match_passed / total_turns * 100) if total_turns > 0 else 0
    
    logger.log(f"\n📊 RAG Evaluation Summary (v8.53 Update)", COLOR_CYAN)
    
    # [v8.53] 시간 포맷팅
    minutes, seconds = divmod(int(overall_duration), 60)
    time_str = f"{minutes}분 {seconds}초" if minutes > 0 else f"{seconds}초"
    
    logger.log(f" - 총 소요 시간: {time_str}")
    logger.log(f" - 통신 에러/타임아웃 횟수: {error_count}건", COLOR_RED if error_count > 0 else None)
    if failed_ids:
        logger.log(f" - 실패한 케이스 목록: [{', '.join(failed_ids)}]", COLOR_RED)
    
    logger.log(f" - Scenario Success Rate (Final): {scenario_success:.1f}% ({scenarios_passed}/{len(test_cases)})")
    logger.log(f" - Total Accuracy Score: {total_final_score:.1f} / {len(test_cases)}.0")
    logger.log(f" - Average Precision: {(total_final_score / len(test_cases) * 100):.1f}%")
    logger.log(f" - Category Identification Rate: {cat_success:.1f}% ({cat_match_passed}/{total_turns})")
    logger.log(f" - T1 Early Identification (Hit/FB/Cat): {t1_success:.1f}% ({t1_passed}/{t1_total})")
    logger.log(f"📄 리포트: {RESULT_MD}")
    logger.log(f"📝 로그 파일: {logger.log_file}")

def save_markdown_report_v3_4(results, scenarios_passed, t1_passed, t1_total, cat_passed, total_turns, total_scenarios, total_score, overall_duration, error_count, failed_ids):
    scenario_success = (scenarios_passed / total_scenarios * 100) if total_scenarios > 0 else 0
    t1_success = (t1_passed / t1_total * 100) if t1_total > 0 else 0
    cat_success = (cat_passed / total_turns * 100) if total_turns > 0 else 0
    avg_precision = (total_score / total_scenarios * 100) if total_scenarios > 0 else 0
    
    # 시간 포맷팅
    minutes, seconds = divmod(int(overall_duration), 60)
    time_str = f"{minutes}분 {seconds}초" if minutes > 0 else f"{seconds}초"

    with open(RESULT_MD, "w", encoding="utf-8") as f:
        f.write("# BaroLaw RAG Evaluation Report (v8.53)\n\n")
        f.write("## 📈 Performance Summary\n\n")
        f.write(f"| Metric | Value |\n| --- | --- |\n")
        f.write(f"| **총 소요 시간** | {time_str} |\n")
        f.write(f"| **통신 에러/타임아웃** | {error_count} 건 |\n")
        f.write(f"| **실패한 케이스 목록** | {', '.join(failed_ids) if failed_ids else '없음'} |\n")
        f.write(f"| **Scenario Success Rate (Final)** | {scenario_success:.1f}% ({scenarios_passed}/{total_scenarios}) |\n")
        f.write(f"| **Total Accuracy Score** | {total_score:.1f} / {total_scenarios}.0 |\n")
        f.write(f"| **Average Precision** | {avg_precision:.1f}% |\n")
        f.write(f"| **Category Match Rate** | {cat_success:.1f}% ({cat_passed}/{total_turns}) |\n")
        f.write(f"| **T1 Identification Rate** | {t1_success:.1f}% ({t1_passed}/{t1_total}) |\n\n")

        f.write("## 📋 Case Details\n\n")
        f.write("| ID | Description | Final | T1 Status | Details (Cat/Sc) |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for r in results:
            last_turn = r["turns"][-1]
            status_icon = "✅" if last_turn["score"] >= 0.8 else "❌"
            
            t1_status = "N/A"
            if len(r["turns"]) > 1:
                t1 = r["turns"][0]
                t1_status = "Hit" if (t1["score"] >= 0.8 or t1["is_uncertain"]) else "Miss"
            
            details = ", ".join([f"T{t['turn']}:{t['score']:.1f}" for t in r["turns"]])
            f.write(f"| {r['id']} | {r['desc']} | {status_icon} | {t1_status} | {details} |\n")

if __name__ == "__main__":
    run_tests()
