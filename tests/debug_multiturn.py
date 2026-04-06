"""
debug_multiturn.py
==================
Phase 23 T2 쿼리 힌트 주입이 실제로 동작하는지 확인하는 진단 스크립트.

1) T1 쿼리 → 서버 응답 → RAG_ENGINE_RESULT 파싱 (어떤 법령을 찾았나)
2) T2 쿼리 → 서버 응답 (같은 session_id 재사용) → RAG_ENGINE_RESULT 파싱
3) 각 단계별 상태+법령명 출력
4) 마지막에 "T1 법령명이 T2 쿼리 힌트로 주입되었는가" 판정

실행 : wsl python3 /home/ksj/BaroLaw/tests/debug_multiturn.py
"""

import json
import requests
import uuid
import urllib.parse
import time

BASE_URL = "http://localhost:8000"

# ─────────────────────────────────────────────
# 진단용 시나리오 (T1 fallback → T2 answer)
# ─────────────────────────────────────────────
SCENARIOS = [
    {
        "id": "DEEP_FRAUD_16_M",
        "turns": [
            {"text": "돈을 빌려줬는데 친구가 안 갚아요.", "expected": "fallback"},
            {"text": "알고보니 처음부터 도박 빚 갚으려 했던 거래요.", "expected": "answer",
             "expected_statutes": ["형법 제347조(사기)"]},
        ]
    },
    {
        "id": "DEEP_FRAUD_18_M",
        "turns": [
            {"text": "회사 장부가 좀 이상한 것 같습니다.", "expected": "fallback"},
            {"text": "CCTV에 직원이 돈을 챙기는 모습이 찍혔어요.", "expected": "answer",
             "expected_statutes": ["형법 제356조(업무상의 횡령과 배임)"]},
        ]
    },
    {
        "id": "DEEP_CRIMINAL_16_M",
        "turns": [
            {"text": "술자리에서 시비가 붙었습니다.", "expected": "fallback"},
            {"text": "제가 먼저 맞았는데 저도 때렸어요.", "expected": "answer",
             "expected_statutes": ["형법 제260조(폭행)", "형법 제257조(상해)"]},
        ]
    },
]

SEP = "─" * 60

def stream_chat(text: str, session_id: str) -> str:
    url = f"{BASE_URL}/chat-stream?text={urllib.parse.quote(text)}&uid=debug_runner&session_id={session_id}"
    full = ""
    try:
        with requests.get(url, stream=True, timeout=180) as r:
            if r.status_code != 200:
                return f"HTTP_ERROR:{r.status_code}"
            for line in r.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8").strip()
                if decoded.startswith("data: "):
                    content = decoded[6:]
                    try:
                        data = json.loads(content)
                        msg = data.get("message", "")
                        full += msg
                        if data.get("done") is True and not msg:
                            break
                    except json.JSONDecodeError:
                        full += content
    except Exception as e:
        return f"EXCEPTION:{e}"
    return full

def extract_rag_result(resp: str) -> str:
    """---[RAG_ENGINE_RESULT]--- 이후 텍스트 추출"""
    marker = "---[RAG_ENGINE_RESULT]---"
    if marker in resp:
        return resp.split(marker)[1].strip().split("\n")[0].strip()
    return "(RAG_ENGINE_RESULT 없음)"

def extract_plain_text(resp: str) -> str:
    return resp.split("---[LEGAL_BASIS]---")[0].strip()

def run():
    print(f"\n{'='*60}")
    print("  Phase 23 T2 힌트 주입 진단 스크립트")
    print(f"{'='*60}\n")

    for scenario in SCENARIOS:
        sid = str(uuid.uuid4())
        print(f"\n{SEP}")
        print(f"🔍 시나리오: {scenario['id']}  (SID: {sid[:8]}...)")
        print(SEP)

        t1_statutes = []  # T1에서 찾은 법령명 (Phase 23 힌트로 사용될 값)

        for idx, turn in enumerate(scenario["turns"]):
            t_num = idx + 1
            text = turn["text"]
            expected = turn["expected"]
            exp_statutes = turn.get("expected_statutes", [])

            print(f"\n  [Turn {t_num}] 쿼리: \"{text}\"")
            print(f"          기대 동작: {expected.upper()}")
            if exp_statutes:
                print(f"          기대 법령: {exp_statutes}")

            t_start = time.time()
            resp = stream_chat(text, sid)
            elapsed = time.time() - t_start

            rag_result = extract_rag_result(resp)
            plain_text = extract_plain_text(resp)

            if "HTTP_ERROR" in resp or "EXCEPTION" in resp:
                print(f"  ❌ 서버 오류: {resp}")
                break

            print(f"\n  ⏱  응답시간: {elapsed:.1f}s")
            print(f"  📦 RAG 엔진 추출 법령: {rag_result}")
            print(f"  💬 답변 첫 줄: {plain_text[:120].replace(chr(10),' ')}...")

            # ── Phase 23 힌트 주입 판정 ──
            if t_num == 1:
                # T1: 법령명 저장
                if rag_result and "없음" not in rag_result:
                    # [v4.1.3] 조문/괄호 제거 로직 강화 (Backend와 일치)
                    raw_names = [s.strip() for s in rag_result.split(",") if s.strip()]
                    t1_statutes = []
                    for n in raw_names:
                        cleaned = n.split(" 제")[0].split("(")[0].strip()
                        if cleaned and len(cleaned) >= 2:
                            t1_statutes.append(cleaned)
                    t1_statutes = list(set(t1_statutes))
                    print(f"\n  ✅ [Phase23] T1 법령명 세션 저장 대상: {t1_statutes}")
                else:
                    print(f"\n  ⚠️  [Phase23] T1에서 법령 미발견 → T2 힌트 없을 것")

            else:
                # T2: 힌트가 실제로 쿼리에 들어갔는지 판정
                print(f"\n  [Phase23] T2 힌트 분석 (v4.1.3 - 보너스 주입)")
                print(f"    T1 저장 법령명: {t1_statutes}")
                
                # 기대 법령 검사 (Fuzzy)
                import re
                found = []
                for s in exp_statutes:
                    # 조문 번호(예: 제260조)만 추출하여 검색 결과에 있는지 확인
                    art_match = re.search(r'제?\s*(\d+)\s*조', s)
                    if art_match:
                        art_num = art_match.group(1)
                        if f"제{art_num}조" in rag_result or f"{art_num}조" in rag_result:
                            found.append(s)
                            continue
                    
                    if s in rag_result or (len(s) >= 2 and s in plain_text):
                        found.append(s)

                if found:
                    print(f"    ✅ T2 기대 법령 검출됨: {found}")
                else:
                    print(f"    ❌ T2 기대 법령 미검출 (기대:{exp_statutes})")
                    print(f"       실제 RAG 결과: {rag_result}")

        print(f"\n{SEP}")

    print(f"\n{'='*60}")
    print("  진단 완료")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    run()
