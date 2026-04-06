from sqlalchemy import create_engine, text
try:
    e = create_engine('postgresql://user:password@localhost:5432/knowledge_db')
    with e.connect() as conn:
        s_count = conn.execute(text('SELECT count(*) FROM statutes')).scalar()
        q_count = conn.execute(text('SELECT count(*) FROM official_qa')).scalar()
        print(f"Statutes count: {s_count}")
        print(f"OfficialQA count: {q_count}")
except Exception as ex:
    print(f"Error: {ex}")
