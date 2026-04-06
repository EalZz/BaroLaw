import json
GOLDEN_PATH = "/home/ksj/BaroLaw/tests/golden_dataset.json"
UPDATES = {
    "CRIMINAL_04_S": {"primary": "스토킹범죄의 처벌 등에 관한 법률", "fallback": ["형법 제319조"]},
    "CRIMINAL_06_S": {"primary": "형법 제366조", "fallback": []},
    "CRIMINAL_18_M": {"primary": "스토킹범죄의 처벌 등에 관한 법률", "fallback": ["형법 제283조"]},
    "CRIMINAL_20_M": {"primary": "형법 제284조", "fallback": []},
    "CRIMINAL_21_M": {"primary": "형법 제314조", "fallback": []},
    "CRIMINAL_24_M": {"primary": "교통사고처리 특례법", "fallback": ["도로교통법 제54조"]},
    "CRIMINAL_26_M": {"primary": "스토킹범죄의 처벌 등에 관한 법률", "fallback": ["형법 제311조"]},
    "CRIMINAL_27_M": {"primary": "통신비밀보호법", "fallback": []},
    "CRIMINAL_28_M": {"primary": "동물보호법", "fallback": []},
    "CRIMINAL_29_M": {"primary": "형법 제276조", "fallback": []},
cat >> /home/ksj/BaroLaw/tests/update_golden.py << 'EOF'
    "TRAFFIC_01_S": {"primary": "특정범죄 가중처벌 등에 관한 법률", "fallback": ["도로교통법 제44조"]},
    "TRAFFIC_03_S": {"primary": "도로교통법 제12조", "fallback": []},
    "TRAFFIC_04_S": {"primary": "도로교통법 제46조의3", "fallback": []},
    "TRAFFIC_05_S": {"primary": "도로교통법 제27조", "fallback": []},
    "TRAFFIC_23_M": {"primary": "자동차손해배상 보장법", "fallback": []},
    "TRAFFIC_27_M": {"primary": "자동차손해배상 보장법", "fallback": []},
    "REAL_ESTATE_02_S": {"primary": "공동주택관리법", "fallback": []},
    "REAL_ESTATE_04_S": {"primary": "민법 제623조", "fallback": []},
    "REAL_ESTATE_06_S": {"primary": "민법 제640조", "fallback": []},
    "REAL_ESTATE_09_S": {"primary": "공동주택관리법", "fallback": []},
    "REAL_ESTATE_12_S": {"primary": "민법", "fallback": []},
    "REAL_ESTATE_24_M": {"primary": "집합건물법", "fallback": []},
    "REAL_ESTATE_29_M": {"primary": "집합건물법", "fallback": []},
}
with open(GOLDEN_PATH, 'r', encoding='utf-8') as f:
    golden = json.load(f)
updated = 0
for test in golden:
    test_id = test.get('test_id', '')
    if test_id in UPDATES:
        update = UPDATES[test_id]
        test['turns'][0]['expected_statutes'] = [update['primary']]
        if update['fallback']:
            test['turns'][0]['fallback_statutes'] = update['fallback']
        updated += 1
        print(f"Updated: {test_id} -> {update['primary']}")
print(f"Total: {updated}")
with open(GOLDEN_PATH, 'w', encoding='utf-8') as f:
    json.dump(golden, f, ensure_ascii=False, indent=2)
print("Done!")
