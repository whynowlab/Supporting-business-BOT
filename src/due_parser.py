import re
from datetime import datetime
from typing import Optional, Tuple

def parse_period(period_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parses a date period string and returns (start_iso, end_iso).
    Supports formats like:
    - YYYY-MM-DD ~ YYYY-MM-DD
    - YYYY.MM.DD ~ YYYY.MM.DD
    - YYYY-MM-DD 18:00 ~ ...
    If parsing fails, returns (None, None).
    """
    if not period_str:
        return None, None
    
    # Cleaning up
    cleaned = period_str.replace('.', '-').strip()
    
    # Try to find a range pattern
    range_match = re.search(r'(\d{4}-\d{2}-\d{2})(?:.*?)~(\s*)(\d{4}-\d{2}-\d{2})', cleaned)
    if range_match:
        start_date = range_match.group(1)
        end_date = range_match.group(3)
        return start_date, end_date
    
    # Single date (maybe end date or just one date)
    # If it looks like a single date, we might treat it as start=end or just start?
    # PRD says "parse apply/receipt periods... based on raw strings".
    # Often single date means deadline.
    single_match = re.search(r'(\d{4}-\d{2}-\d{2})', cleaned)
    if single_match:
        # If there's only one date, it's ambiguous. 
        # But for 'due' logic, usually the end date matters most.
        # Let's return it as end date if we can't find a start.
        # Or maybe it's the start date?
        # Let's assume if it's a deadline, it might be the end.
        # But let's look at context. "2023-01-01" -> 
        # For safety, let's just return it as BOTH start and end? or None/date?
        # Let's return (date, date) for safety for filtering?
        # Actually PRD says: "If parsing fails: store raw strings; do NOT crash; skip due-soon classification".
        # So maybe better to be strict?
        # Let's return (None, None) if not a clear range?
        # But "2023-12-31까지" is common. 
        return single_match.group(1), single_match.group(1)
        
    return None, None

def parse_iso(date_str: str) -> Optional[str]:
    """Helper to ensure ISO format YYYY-MM-DD"""
    if not date_str:
        return None
    match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str.replace('.', '-'))
    if match:
        return match.group(1)
    return None
