import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Any

DB_PATH = os.getenv("DB_PATH", "data/bot.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. programs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS programs (
        program_key TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        source TEXT NOT NULL,
        seq TEXT NOT NULL,
        title TEXT,
        summary_raw TEXT,
        agency TEXT,
        category_l1 TEXT,
        region_raw TEXT,
        apply_period_raw TEXT,
        apply_start_at TEXT,
        apply_end_at TEXT,
        event_period_raw TEXT,
        event_start_at TEXT,
        event_end_at TEXT,
        url TEXT,
        created_at_source TEXT,
        updated_at_source TEXT,
        ingested_at TEXT
    )
    """)

    # 2. company_profile table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_profile (
        id INTEGER PRIMARY KEY CHECK(id=1),
        region_allow TEXT,
        interests TEXT,
        include_keywords TEXT,
        exclude_keywords TEXT,
        min_score INTEGER DEFAULT 60,
        notify_enabled INTEGER DEFAULT 1,
        notify_time_kst TEXT DEFAULT '08:30',
        due_days_threshold INTEGER DEFAULT 7
    )
    """)

    # 3. user_actions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_actions (
        program_key TEXT,
        action TEXT,
        created_at TEXT,
        UNIQUE(program_key, action)
    )
    """)

    # 4. ingestion_runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_runs (
        run_at TEXT,
        kind TEXT,
        fetched_count INTEGER,
        new_count INTEGER,
        updated_count INTEGER,
        error TEXT
    )
    """)

    # Initialize default profile if running for the first time
    cursor.execute("SELECT count(*) FROM company_profile WHERE id=1")
    if cursor.fetchone()[0] == 0:
        default_profile = (
            1,
            json.dumps(["전국"], ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            60,
            1,
            "08:30",
            7
        )
        cursor.execute("""
        INSERT INTO company_profile (id, region_allow, interests, include_keywords, exclude_keywords, min_score, notify_enabled, notify_time_kst, due_days_threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_profile)

    conn.commit()
    conn.close()

def upsert_program(program_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    
    keys = list(program_data.keys())
    placeholders = ",".join(["?"] * len(keys))
    columns = ",".join(keys)
    updates = ",".join([f"{k}=excluded.{k}" for k in keys if k != 'program_key'])
    
    sql = f"""
    INSERT INTO programs ({columns}) VALUES ({placeholders})
    ON CONFLICT(program_key) DO UPDATE SET {updates}
    """
    
    cursor.execute(sql, list(program_data.values()))
    conn.commit()
    conn.close()

def get_profile():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company_profile WHERE id=1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_profile(updates: dict):
    conn = get_connection()
    cursor = conn.cursor()
    
    set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
    values = list(updates.values())
    
    sql = f"UPDATE company_profile SET {set_clause} WHERE id=1"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()

def log_ingestion_run(run_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    
    keys = list(run_data.keys())
    placeholders = ",".join(["?"] * len(keys))
    columns = ",".join(keys)
    
    sql = f"INSERT INTO ingestion_runs ({columns}) VALUES ({placeholders})"
    cursor.execute(sql, list(run_data.values()))
    conn.commit()
    conn.close()
