"""
Centralized constants for the SaulGPT scraper.
"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Connection": "keep-alive",
}

INDIACODE_BASE_URL = "https://www.indiacode.nic.in"
KANOON_BASE_URL = "https://indiankanoon.org"

# Delay ranges for polite scraping (seconds)
MIN_DELAY = 2.0
MAX_DELAY = 6.0

DEFAULT_RETRIES = 3
TIMEOUT = 15
