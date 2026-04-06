import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.abspath('/home/ksj/BaroLaw/backend'))

from preprocessor import LegalPreprocessor

async def test_preprocessor():
    p = LegalPreprocessor()
    test_cases = [
        "회삿돈을 개인 주식 투자에 썼다가 반 정도 날렸어요. 어떻게 하죠?",
        "회사 장부가 좀 이상한 것 같습니다.",
        "친구한테 생활비라고 500 빌려줬는데 알고보니 도박에 다 썼대요. 고소 되나요?"
    ]
    
    for case in test_cases:
        print(f"\n[Test Case]: {case}")
        intent = await p.analyze(case)
        print(f"Category: {intent.category}")
        print(f"Keywords: {intent.legal_keywords}")
        print(f"Summary: {intent.factual_summary}")
        print(f"Is Multiturn: {intent.is_multiturn_continuation}")
        print(f"Missing Info: {intent.missing_info_request}")

if __name__ == "__main__":
    os.environ["OLLAMA_HOST"] = "localhost" # Adjust if necessary
    asyncio.run(test_preprocessor())
