import re
import hashlib
import time
import random
import logging
import requests
from typing import Optional
from .constants import HEADERS, MIN_DELAY, MAX_DELAY, DEFAULT_RETRIES, TIMEOUT

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Standardizes whitespace and trims text."""
    return re.sub(r'\s+', ' ', text).strip()

def get_text_hash(text: str) -> str:
    """Generates a SHA-256 hash of the text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def is_valid_section(text: str) -> bool:
    """Checks if the text looks like a valid legal section."""
    return bool(re.search(r'\b(Section|Article|Sec\.)\s+\d+', text, re.I)) and len(text) > 200

def polite_fetch(url: str, session: requests.Session, retries: int = DEFAULT_RETRIES) -> Optional[str]:
    """Fetch a page with randomized delays and retry logic."""
    for i in range(retries):
        try:
            # Randomized delay to avoid being blocked
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            time.sleep(delay)
            
            resp = session.get(url, headers=HEADERS, timeout=TIMEOUT)
            
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                logger.warning(f"403 Forbidden for {url}. Backing off.")
                time.sleep(10 * (i + 1))
            elif resp.status_code == 404:
                logger.warning(f"404 Not Found for {url}")
                return None
            else:
                logger.warning(f"HTTP {resp.status_code} for {url}")
                
        except Exception as e:
            logger.warning(f"Attempt {i+1} failed for {url}: {e}")
            
    return None
