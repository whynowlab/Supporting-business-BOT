import pytest
import os
from src.db import init_db, get_connection
from src.telegram_bot import action_handler # Hard to test handler directly without mock Update
from datetime import datetime

# Logic for testing DB persistence of actions
def test_user_actions_persistence():
    # Setup clean DB
    if os.path.exists("data/bot_test.db"):
        os.remove("data/bot_test.db")
    
    # Override DB path env for test?
    # src.db uses DB_PATH from os.getenv.
    os.environ["DB_PATH"] = "data/bot_test.db"
    init_db()
    
    conn = get_connection()
    c = conn.cursor()
    
    # Simulate saving an action
    c.execute("INSERT INTO user_actions (program_key, action, created_at) VALUES (?, ?, ?)", 
              ("support:100", "saved", datetime.now().isoformat()))
    conn.commit()
    
    # Verify
    c.execute("SELECT * FROM user_actions WHERE program_key='support:100'")
    row = c.fetchone()
    assert row['action'] == "saved"
    
    # Cleanup
    conn.close()
    if os.path.exists("data/bot_test.db"):
        os.remove("data/bot_test.db")
