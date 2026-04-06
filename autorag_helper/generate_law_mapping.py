import json
import os
import sys
from sqlalchemy import create_engine, text

# 기본 KNOWLEDGE_DB_URL (WSL 내 Docker 브리지 기준)
# WSL 내부에서 실행 시 'localhost'는 호스트를 의미할 수 있으므로 'db' 호스트가 아니면 대체 시도 방지
KNOWLEDGE_DB_URL = os.getenv("KNOWLEDGE_DB_URL", "postgresql://user:password@localhost:5432/knowledge_db")

def generate_mapping():
    print(f"Connecting to database at {KNOWLEDGE_DB_URL}...")
    try:
        # DB 연결 엔진 생성
        engine = create_engine(KNOWLEDGE_DB_URL)
        with engine.connect() as connection:
            # 모든 정식 법령 데이터를 가져옴 (id, law_name, article)
            query = text("SELECT id, law_name, article FROM statutes")
            result = connection.execute(query)
            
            mapping = {}
            count = 0
            for row in result:
                # row[0]: id, row[1]: law_name, row[2]: article
                # 포맷: "형법 제347조(사기)"
                law_name = row[1] if row[1] else ""
                article = row[2] if row[2] else ""
                
                # 법령명과 조항 사이의 공백 처리를 통해 "형법 제347조(사기)" 형태 구축
                law_full_name = f"{law_name} {article}".strip()
                
                if law_full_name:
                    mapping[law_full_name] = str(row[0]) # AutoRAG gt 호환용 문자열 ID
                    count += 1
            
            # 저장 경로 설정 (현재 스크립트 위치 기준 상위 backend 폴더)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_path = os.path.join(base_dir, 'backend', 'law_mapping.json')
            
            # 디렉토리가 없을 수도 있으니 확인 (backend는 보통 존재함)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
            
            print(f"Successfully generated mapping for {count} items at {output_path}")

    except Exception as e:
        print(f"[ERROR] Failed to generate mapping: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_mapping()
