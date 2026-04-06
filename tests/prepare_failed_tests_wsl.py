import json
import re
import os

BASE_DIR = "/home/ksj/BaroLaw/tests"
DATASET_PATH = os.path.join(BASE_DIR, "golden_dataset_backup_20260310.json")
RESULTS_PATH = os.path.join(BASE_DIR, "test_results.md")
OUTPUT_PATH = os.path.join(BASE_DIR, "golden_dataset.json")

def get_failed_ids():
    failed_ids = []
    if not os.path.exists(RESULTS_PATH):
        return []
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        # Find rows with ❌ FAIL
        matches = re.finditer(r"\| (.*?) \|.*?\| ❌ FAIL \|", content)
        for m in matches:
            failed_ids.append(m.group(1).strip())
    return failed_ids

def main():
    failed_ids = get_failed_ids()
    print(f"Detected {len(failed_ids)} failed cases.")
    
    if not os.path.exists(DATASET_PATH):
        print(f"Backup file not found: {DATASET_PATH}")
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        original_data = json.load(f)
    
    focused_data = [case for case in original_data if case["test_id"] in failed_ids]
    
    # Add +a (New tricky cases for failed domains)
    extra_cases = [
        {
            "test_id": "DEBUG_FRAUD_ADD_01",
            "category": "FRAUD",
            "description": "보험 가짜 사고 유도 (보험사기 정밀검증)",
            "turns": [
                {
                    "turn_id": 1,
                    "user_input": "지인이 돈 필요하니까 가짜로 사고 나서 보험금 타먹자고 꼬시는데, 이거 응하면 저도 처벌받나요?",
                    "expected_action": "answer",
                    "expected_statutes": ["보험사기방지 특별법"]
                }
            ]
        },
        {
            "test_id": "DEBUG_CRIMINAL_ADD_02",
            "category": "CRIMINAL",
            "description": "업무방해 vs 주거침입 (가게 행패)",
            "turns": [
                {
                    "turn_id": 1,
                    "user_input": "취객이 가게 앞에서 안 비키고 계속 욕설하면서 장사를 방해하고 있어요. 이거 무슨 죄인가요?",
                    "expected_action": "answer",
                    "expected_statutes": ["업무방해"]
                }
            ]
        },
        {
            "test_id": "DEBUG_TRAFFIC_ADD_03",
            "category": "TRAFFIC",
            "description": "비접촉 사고 뺑소니 (구호조치 의무)",
            "turns": [
                {
                    "turn_id": 1,
                    "user_input": "제가 차선 변경을 했는데 뒤에 오던 할아버지가 놀라서 혼자 넘어지셨어요. 전 안 부딪혔으니까 그냥 가도 되죠?",
                    "expected_action": "answer",
                    "expected_statutes": ["도로교통법", "도주치사상", "구호조치"]
                }
            ]
        }
    ]
    
    focused_data.extend(extra_cases)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(focused_data, f, ensure_ascii=False, indent=4)
    
    print(f"Created focused dataset with {len(focused_data)} cases.")

if __name__ == "__main__":
    main()
