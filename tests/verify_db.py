from src.db import init_db, get_connection, upsert_program, get_profile, update_profile
import os

def test_db():
    if os.path.exists("data/bot.db"):
        os.remove("data/bot.db")
    
    init_db()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check tables
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    assert "programs" in table_names
    assert "company_profile" in table_names
    assert "user_actions" in table_names
    assert "ingestion_runs" in table_names
    
    # Check default profile
    profile = get_profile()
    assert profile['id'] == 1
    assert profile['min_score'] == 60
    
    # Test upsert
    program = {
        "program_key": "support:123",
        "kind": "support",
        "source": "bizinfo",
        "seq": "123",
        "title": "Test Program"
    }
    upsert_program(program)
    
    cursor.execute("SELECT * FROM programs WHERE program_key='support:123'")
    row = cursor.fetchone()
    assert row['title'] == "Test Program"
    
    print("DB verification passed!")

if __name__ == "__main__":
    test_db()
