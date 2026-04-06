import requests
import re

url = "https://www.easylaw.go.kr/CSP/OnhunqueansLstPopRetrieve.laf?csmSeq=684"
r = requests.get(url)
text = r.text

# .laf로 끝나는 AJAX 호출 패턴들을 찾아봅/니다.
# 주로 $.post('URL', {params...}) 또는 .load('URL') 등
patterns = re.findall(r"[\w/]+\.laf", text)
print("--- Found .laf URLs ---")
for p in set(patterns):
    print(p)

# showSmgSummToggle1 근처의 구체적인 호출부 추출
match = re.search(r"function showSmgSummToggle1.*?\{(.*?)\}", text, re.DOTALL)
if match:
    func_body = match.group(1)
    print("\n--- showSmgSummToggle1 Body ---")
    print(func_body)
else:
    print("\nFunction body not found via regex")
