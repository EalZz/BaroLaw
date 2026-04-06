import os
import sys
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Probe")

try:
    logger.info("Step 1: Importing Transformers & Torch...")
    from transformers import AutoModel, AutoTokenizer
    import torch
    
    model_id = "jhgan/ko-sroberta-multitask"
    logger.info(f"Step 2: Loading Tokenizer for {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    
    logger.info(f"Step 3: Loading Model {model_id}...")
    model = AutoModel.from_pretrained(model_id)
    
    logger.info("Step 4: Testing minimal embedding...")
    text = "법률 상담 제도를 알려줘."
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    
    logger.info("SUCCESS: Local Semantic Engine is healthy!")
    sys.exit(0)

except Exception as e:
    logger.error(f"FAILED at some point: {e}")
    sys.exit(1)
