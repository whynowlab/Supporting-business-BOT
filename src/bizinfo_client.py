import os
import requests
import json
import xmltodict
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

SUPPORT_API_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
EVENT_API_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoEventApi.do"

class BizinfoClient:
    def __init__(self):
        self.support_key = os.getenv("BIZINFO_SUPPORT_KEY")
        self.event_key = os.getenv("BIZINFO_EVENT_KEY")
    
    def _fetch(self, url: str, api_key: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        if not api_key:
            logger.warning("API key not provided for %s", url)
            return []
            
        base_params = {
            "crtfcKey": api_key,
            "dataType": "json",
            "searchCnt": 100  # Fetch a reasonable batch
        }
        if params:
            base_params.update(params)
            
        # Try JSON
        try:
            response = requests.get(url, params=base_params, timeout=10)
            response.raise_for_status()
            
            # Check if response is actually JSON (sometimes APIs return XML even if dataType=json on error or quirk)
            try:
                data = response.json()
                # Structure: { "jsonArray": [ ... ] } usually
                items = data.get("jsonArray", [])
                if items:
                    return items
            except json.JSONDecodeError:
                logger.info("JSON decode failed, attempting XML fallback for %s", url)
                pass # Fallback to XML
        except Exception as e:
            logger.error(f"Error fetching JSON from {url}: {e}")
            # Depending on error, we might want to fail or try XML. 
            # If 404/500, XML might not help. But if content-type issue, maybe.
            pass

        # Fallback to XML (remove dataType=json)
        base_params.pop("dataType", None)
        try:
            response = requests.get(url, params=base_params, timeout=10)
            response.raise_for_status()
            
            # Parse XML
            xml_data = xmltodict.parse(response.content)
            # Structure: <rss><channel><item>...</item></channel></rss>
            # OR <response><body><items>...
            # Bizinfo RSS usually: rss -> channel -> item (list or dict)
            
            rss = xml_data.get('rss', {})
            channel = rss.get('channel', {})
            items = channel.get('item', [])
            
            if isinstance(items, dict):
                return [items]
            elif isinstance(items, list):
                return items
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error fetching/parsing XML from {url}: {e}")
            return []

    def fetch_support_programs(self) -> List[Dict[str, Any]]:
        return self._fetch(SUPPORT_API_URL, self.support_key)

    def fetch_events(self) -> List[Dict[str, Any]]:
        return self._fetch(EVENT_API_URL, self.event_key)
