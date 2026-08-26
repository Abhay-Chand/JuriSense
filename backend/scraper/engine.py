import logging
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict, Optional
from .constants import INDIACODE_BASE_URL, KANOON_BASE_URL
from .utils import polite_fetch, clean_text, get_text_hash, is_valid_section

logger = logging.getLogger(__name__)

class BaseScraper:
    def __init__(self, session: requests.Session):
        self.session = session

    def scrape(self, act_name: str) -> List[Dict]:
        raise NotImplementedError("Subclasses must implement scrape()")

class IndiaCodeScraper(BaseScraper):
    def find_handle(self, act_name: str) -> Optional[str]:
        search_url = f"{INDIACODE_BASE_URL}/search?query={act_name.replace(' ', '+')}"
        html = polite_fetch(search_url, self.session)
        if not html: return None
        
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "/handle/123456789/" in a['href']:
                return urljoin(INDIACODE_BASE_URL, a['href'])
        return None

    def scrape(self, act_name: str) -> List[Dict]:
        sections = []
        handle_url = self.find_handle(act_name)
        if not handle_url:
            logger.info(f"IndiaCode: No handle found for {act_name}")
            return []

        html = polite_fetch(handle_url, self.session)
        if not html: return []
        
        soup = BeautifulSoup(html, 'html.parser')
        sub_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if "/handle/123456789/" in href and href not in handle_url:
                sub_links.append(urljoin(INDIACODE_BASE_URL, href))
        
        sub_links = list(dict.fromkeys(sub_links))
        logger.info(f"IndiaCode: Found {len(sub_links)} sub-links for {act_name}")

        for link in sub_links[:100]: # Safety cap
            page_html = polite_fetch(link, self.session)
            if not page_html: continue
            
            page_soup = BeautifulSoup(page_html, 'html.parser')
            if any(x in page_soup.get_text() for x in ["Browsing Central Act", "Sort by", "Items/Page"]):
                continue
                
            content_div = page_soup.find("div", {"id": "content"}) or page_soup.find("div", class_="item-body")
            if not content_div: continue
            
            text = clean_text(content_div.get_text())
            if not is_valid_section(text): continue
                
            match = re.search(r'(Section|Sec\.|Article)\s+(\d+[A-Z]*)', text, re.I)
            sec_num = match.group(2) if match else "0"
            
            title_el = page_soup.find("h1") or page_soup.find("h2") or page_soup.find("title")
            title = clean_text(title_el.get_text()) if title_el else f"Section {sec_num}"
            
            sections.append({
                "section_number": sec_num,
                "title": title,
                "text": text,
                "hash": get_text_hash(text)
            })
            
        return sections

class KanoonScraper(BaseScraper):
    def scrape(self, act_name: str) -> List[Dict]:
        sections = []
        search_url = f"{KANOON_BASE_URL}/search/?formInput={act_name.replace(' ', '+')}+doctypes:acts"
        html = polite_fetch(search_url, self.session)
        if not html: return []
        
        soup = BeautifulSoup(html, 'html.parser')
        results = soup.select('.result_title a')
        if not results: return []
        
        act_url = urljoin(KANOON_BASE_URL, results[0]['href'])
        html = polite_fetch(act_url, self.session)
        if not html: return []
        
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.find("div", class_="judgments")
        if not content: return []
        
        links = content.find_all('a', href=True)
        doc_links = [urljoin(KANOON_BASE_URL, a['href']) for a in links if "/doc/" in a['href'] and not a['href'].endswith("/")]
        
        if len(doc_links) > 2:
            logger.info(f"Kanoon: TOC detected for {act_name}. Following {len(doc_links)} links.")
            for link in doc_links:
                sec_html = polite_fetch(link, self.session)
                if not sec_html: continue
                sec_soup = BeautifulSoup(sec_html, 'html.parser')
                sec_div = sec_soup.find("div", class_="judgments")
                if not sec_div: continue
                
                text = clean_text(sec_div.get_text())
                if not is_valid_section(text): continue
                
                title_el = sec_soup.find("div", class_="doc_title") or sec_soup.find("h1")
                title = clean_text(title_el.get_text()) if title_el else "Section Content"
                
                match = re.search(r'(Section|Sec\.|Article)\s+(\d+[A-Z]*)', title, re.I)
                sec_num = match.group(2) if match else str(len(sections)+1)
                
                sections.append({
                    "section_number": sec_num,
                    "title": title,
                    "text": text,
                    "hash": get_text_hash(text)
                })
        return sections

class LegalScraperEngine:
    def __init__(self):
        self.session = requests.Session()
        self.indiacode = IndiaCodeScraper(self.session)
        self.kanoon = KanoonScraper(self.session)

    def scrape_act(self, act_name: str) -> tuple[List[Dict], str]:
        """Try IndiaCode first, then Kanoon as fallback."""
        logger.info(f"Starting scrape for: {act_name}")
        
        sections = self.indiacode.scrape(act_name)
        if len(sections) >= 3:
            return sections, "IndiaCode"
            
        logger.info(f"IndiaCode failed/insufficient for {act_name}. Trying Kanoon fallback.")
        sections = self.kanoon.scrape(act_name)
        if sections:
            return sections, "IndianKanoon"
            
        return [], "None"
