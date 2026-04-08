import os
import yaml
import logging

logger = logging.getLogger("ConfigLoader")

# 설정 파일 경로 (backend 디렉토리 내 rag_config.yaml)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "rag_config.yaml")

def load_config():
    """rag_config.yaml 파일을 로드합니다."""
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file not found: {CONFIG_PATH}")
        return {}
        
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")
        return {}

# 전역 설정 객체
config = load_config()

def get_config():
    return config
