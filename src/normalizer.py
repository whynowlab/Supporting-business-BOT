from datetime import datetime
import json
from .due_parser import parse_period
from typing import Dict, Any

def normalize_support(item: Dict[str, Any]) -> Dict[str, Any]:
    # Item keys based on Bizinfo JSON response (may vary, need to be robust)
    # Common keys: pblancId, pblancNm, reqstBeginEndDe, reqstDt, creatPnttm, etc.
    # We map them to our schema.
    
    seq = item.get('pblancId', '')
    title = item.get('pblancNm', '')
    
    # Periods
    # 'reqstBeginEndDe' usually contains "YYYY-MM-DD ~ YYYY-MM-DD"
    apply_period_raw = item.get('reqstBeginEndDe') or item.get('reqstDt')
    start_at, end_at = parse_period(apply_period_raw)
    
    return {
        "program_key": f"support:{seq}",
        "kind": "support",
        "source": "bizinfo",
        "seq": seq,
        "title": title,
        "summary_raw": item.get('pblancSumry') or item.get('pblancCn'), # Summary or Content
        "agency": item.get('jrsdinstNm') or item.get('excInsttNm'), # Jurisdiction or Executing Inst
        "category_l1": item.get('pblancClCd'), # Classification Code (mapped if needed, or raw)
        "region_raw": item.get('jrsdinstNm'), # Often region is implied by agency or separate field
        "apply_period_raw": apply_period_raw,
        "apply_start_at": start_at,
        "apply_end_at": end_at,
        "url": item.get('inqireUrl') or f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={seq}", # Prefer API URL
        # Note: Generic URL might be AS/74/view.do or A/105/view.do. The 'AS/74' part seems more common in recent docs.
        # But let's try to just search "bizinfo.go.kr" if all else fails? No.
        # Best bet: Use 'inqireUrl' field from API if present.
        "created_at_source": item.get('creatPnttm'), # "YYYY-MM-DD HH:MM:SS"
        "updated_at_source": None, # Usually not provided clearly
        "ingested_at": datetime.now().isoformat()
    }

def normalize_event(item: Dict[str, Any]) -> Dict[str, Any]:
    # Event keys: eventId, eventNm, eventPeriod, rceptPd, etc.
    seq = item.get('eventId', '')
    title = item.get('eventNm', '')
    
    # Periods
    # rceptPd is receipt period (apply)
    # eventPeriod is event period
    apply_period_raw = item.get('rceptPd')
    apply_start, apply_end = parse_period(apply_period_raw)
    
    event_period_raw = item.get('eventPeriod')
    event_start, event_end = parse_period(event_period_raw)
    
    return {
        "program_key": f"event:{seq}",
        "kind": "event",
        "source": "bizinfo",
        "seq": seq,
        "title": title,
        "summary_raw": item.get('eventCn'),
        "agency": item.get('insttNm'),
        "category_l1": "행사", # Default for events
        "region_raw": item.get('areaNm'),
        "apply_period_raw": apply_period_raw,
        "apply_start_at": apply_start,
        "apply_end_at": apply_end,
        "event_period_raw": event_period_raw,
        "event_start_at": event_start,
        "event_end_at": event_end,
        "url": item.get('inqireUrl') or f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C127/AS/73/view.do?pblancId={seq}", 
        # API often returns valid URL in 'inqireUrl' or 'url'.
        # Fallback to S1T122C127/AS/73 based on search trends for events?
        
        "created_at_source": item.get('regDate'),
        # Actually Event URL is likely different. Let's start with this or try to find pattern.
        # Fallback to general search if unsure? PRD doesn't specify URL construction, but usually reliable.
        # Check if item has 'link'?
        "created_at_source": item.get('regDate'),
        "updated_at_source": None,
        "ingested_at": datetime.now().isoformat()
    }
