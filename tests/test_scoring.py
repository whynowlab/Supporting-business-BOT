import pytest
import json
from src.filters import calculate_score, is_recommended
from datetime import datetime, timedelta

@pytest.fixture
def profile():
    return {
        "interests": json.dumps(["AI", "Data"]),
        "include_keywords": json.dumps(["Startup", "Global"]),
        "exclude_keywords": json.dumps(["Spam"]),
        "region_allow": json.dumps(["Seoul"]),
        "min_score": 60,
        "due_days_threshold": 7
    }

def test_score_interest_match(profile):
    program = {
        "title": "AI Support Program",
        "summary_raw": "For Data Science",
        "category_l1": "IT"
    }
    score, reasons = calculate_score(program, profile)
    # Base 5 + Interest 25 = 30.
    # Wait, title has "AI" (match), summary has "Data" (match). Only counts once?
    # Logic: "if interest_hit: score += 25".
    # So 30.
    assert score >= 30
    assert "관심분야 일치" in reasons

def test_score_keyword_match(profile):
    program = {
        "title": "Global Startup Challenge",
        "summary_raw": "..."
    }
    score, reasons = calculate_score(program, profile)
    # Base 5
    # Include: Startup (+10), Global (+10). Total +20.
    # Total 25.
    assert score == 25
    assert "키워드 매칭(2건)" in reasons

def test_score_due_soon(profile):
    # Mock date
    today = datetime.now()
    due_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
    
    program = {
        "title": "Normal Program",
        "apply_end_at": due_date,
        "kind": "support"
    }
    score, reasons = calculate_score(program, profile)
    # Base 5 + Due 15 = 20.
    assert score == 20
    assert any("마감 임박" in r for r in reasons)

def test_exclude(profile):
    program = {
        "title": "Spam Program",
        "summary_raw": "..."
    }
    recommended, score, reasons = is_recommended(program, profile)
    assert not recommended
    assert score == 0
