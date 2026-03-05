import requests
import re

url = "https://www.easylaw.go.kr/CSP/OnhunqueansLstPopRetrieve.laf?csmSeq=684"
r = requests.get(url)
text = r.text

# showSmgSummToggle1 함수 시작 지점 찾기
start = text.find('function showSmgSummToggle1')
if start != -1:
    # 대략 3000자 정도 추출하여 함수 내용을 읽어봄
    print(text[start:start+3000])
else:
    print("Function not found")
