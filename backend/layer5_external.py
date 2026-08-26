"""
SAULSGPT — LAYER 5: EXTERNAL TOOLS
=====================================
Two tools:

Tool 1 — IndiaKanoon Case Law Fetcher
  Scrapes indiankanoon.org for relevant judgments
  Called AFTER Layer 3 for Case Analysis mode only
  Appended to final response as supplementary section
  Gracefully skipped if offline or blocked

Tool 2 — APScheduler Background Auto-Updater
  Re-runs scraper + chunk_and_embed every 30 days
  Keeps ChromaDB current with latest amendments
  Runs as background daemon
  Called once when FastAPI server starts

Run standalone to test IndiaKanoon:
    python layer5_external.py

Import in orchestrator:
    from layer5_external import fetch_case_law, start_auto_updater
"""

import os
import time
import subprocess
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

# DuckDuckGo search — free, no API key needed
# Install: pip install duckduckgo-search
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    print("[Layer 5] WARNING: duckduckgo-search not installed.")
    print("          Run: pip install duckduckgo-search")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

# Absolute paths for subprocess updater
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
REPO_DIR    = os.path.dirname(BASE_DIR)
SCRAPER     = os.path.join(BASE_DIR, "01_scraper.py")
CHUNKER     = os.path.join(BASE_DIR, "02_chunk_and_embed.py")

# IndiaKanoon config
IK_BASE_URL = "https://indiankanoon.org"
IK_TIMEOUT  = 8    # seconds — don't block main pipeline long
IK_MAX_RESULTS = 2 # only top 2 judgments

# Browser User-Agent — required to avoid being blocked
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-IN,en;q=0.9",
}


# ─────────────────────────────────────────────────────────────
# TOOL 1 — INDIAKANOON CASE LAW FETCHER
# ─────────────────────────────────────────────────────────────

def fetch_case_law(
    query: str,
    act_name: str = "",
    section_num: str = ""
) -> str:
    """
    Fetches relevant Supreme Court / High Court judgments
    from IndiaKanoon for the given legal query.

    Called AFTER Layer 3 generates response.
    Result is APPENDED to final response — not used for reasoning.
    This avoids polluting the LLM context with unverified web data.

    Args:
        query      : user's legal query (reformulated from Layer 1)
        act_name   : act name from retrieved sections (improves search)
        section_num: section number from retrieved sections

    Returns:
        formatted string of top cases to append to response
        OR empty string if offline/blocked/no results

    Example:
        result = fetch_case_law(
            "employer unpaid wages",
            act_name="Payment of Wages Act",
            section_num="15"
        )
    """
    print("[Layer 5] 🌐 Fetching relevant case law from IndiaKanoon...")

    # 1. Clean database act name
    # ChromaDB stores names like "NIA_from_db" — IndiaKanoon won't understand
    # Strip "_from_db" suffix and underscores before searching
    clean_act = act_name.replace("_from_db", "").replace("_", " ").strip()

    # 2. Map common acronyms to full act names IndiaKanoon recognises
    ACT_MAP = {
        "NIA":  "Negotiable Instruments Act",
        "IPC":  "Indian Penal Code",
        "CRPC": "Criminal Procedure Code",
        "CrPC": "Criminal Procedure Code",
        "BNS":  "Bharatiya Nyaya Sanhita",
        "BNSS": "Bharatiya Nagarik Suraksha Sanhita",
        "BSA":  "Bharatiya Sakshya Adhiniyam",
        "CPC":  "Civil Procedure Code",
        "IEA":  "Indian Evidence Act",
        "HMA":  "Hindu Marriage Act",
        "MVA":  "Motor Vehicles Act",
        "IDA":  "Industrial Disputes Act",
    }
    search_act = ACT_MAP.get(clean_act.upper(), clean_act)

    # 3. Build STRICT search query — no user story, just law
    # Long user queries choke IndiaKanoon keyword search
    # Only use act name + section number for precise results
    if search_act and section_num:
        search_query = f'"{search_act}" AND "Section {section_num}"'
    elif search_act:
        search_query = f'"{search_act}"'
    else:
        # Fallback: first 4 words of query only
        search_query = " ".join(query.split()[:4])

    print(f"[Layer 5] Search query: {search_query}")

    search_url = (
        f"{IK_BASE_URL}/search/"
        f"?formInput={requests.utils.quote(search_query)}"
        f"&type=judgments"
    )

    try:
        response = requests.get(
            search_url,
            headers=HEADERS,
            timeout=IK_TIMEOUT
        )
        response.raise_for_status()

        soup    = response.text
        bsoup   = BeautifulSoup(soup, 'html.parser')

        # IndiaKanoon search result structure
        # Try multiple selectors — site structure can vary
        results = (
            bsoup.find_all('div', class_='result', limit=IK_MAX_RESULTS) or
            bsoup.find_all('div', class_='result_title', limit=IK_MAX_RESULTS) or
            bsoup.find_all('li', class_='result', limit=IK_MAX_RESULTS)
        )

        if not results:
            print("[Layer 5] ℹ️  No case law results found.")
            return ""

        cases = []
        for idx, res in enumerate(results, 1):
            try:
                # Try to extract title
                title_container = (
                    res.find('div', class_='result_title') or
                    res.find('a') or
                    res
                )
                title_tag = (
                    title_container.find('a')
                    if title_container.name != 'a'
                    else title_container
                )

                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                href  = title_tag.get('href', '')
                link  = f"{IK_BASE_URL}{href}" if href.startswith('/') else href

                # Try to extract snippet
                snippet_tag = (
                    res.find('div', class_='headline') or
                    res.find('div', class_='snippet') or
                    res.find('p')
                )
                snippet = (
                    snippet_tag.get_text(strip=True)[:200]
                    if snippet_tag
                    else "See full judgment at link."
                )

                cases.append(
                    f"Case {idx}: {title}\n"
                    f"  Summary: {snippet}\n"
                    f"  Link: {link}"
                )

            except Exception:
                # Skip malformed result — don't crash
                continue

        if not cases:
            return ""

        result_block = (
            "\n\n📚 RELEVANT CASE LAW (IndiaKanoon)\n"
            + "─" * 40 + "\n"
            + "\n\n".join(cases)
            + "\n" + "─" * 40
            + "\nNote: Case law provided for reference only. "
              "Verify judgments before citing."
        )

        print(f"[Layer 5] ✅ Found {len(cases)} relevant case(s).")
        return result_block

    except requests.exceptions.Timeout:
        print("[Layer 5] ⚠️  IndiaKanoon request timed out.")
        return ""

    except requests.exceptions.ConnectionError:
        print("[Layer 5] ⚠️  No internet connection. Skipping case law.")
        return ""

    except requests.exceptions.HTTPError as e:
        print(f"[Layer 5] ⚠️  IndiaKanoon HTTP error: {e}")
        return ""

    except Exception as e:
        print(f"[Layer 5] ⚠️  Case law fetch error: {e}")
        return ""


# ─────────────────────────────────────────────────────────────
# TOOL 2 — BACKGROUND AUTO-UPDATER
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# TOOL 2 — AGENTIC FALLBACK WEB SEARCH
# Triggered ONLY when Layer 2 ChromaDB returns zero results
# AND Knowledge Graph also found nothing
# Searches the web for Indian law info on the query
# Formats results to look like ChromaDB chunks
# So Layer 3 reads them without knowing the difference
# ─────────────────────────────────────────────────────────────

def fallback_web_search(query: str) -> list:
    """
    Safety net when local database has no relevant data.
    Searches the live web for Indian law information.
    Formats results to mimic ChromaDB chunks so Layer 3
    can process them exactly like local database results.

    Triggered by orchestrator ONLY when:
    1. Layer 2 returns zero results AND
    2. Knowledge Graph found no relationships

    This guarantees SaulGPT always finds an answer
    even if local database is incomplete.

    Args:
        query: user query (reformulated from Layer 1)

    Returns:
        list of mock chunk dicts matching ChromaDB format
        OR empty list if web search also fails

    Example:
        results = fallback_web_search(
            "Industrial Disputes Act retrenchment definition"
        )
        # Returns list of dicts with act_name, section_number,
        # is_repealed, content — same format as ChromaDB chunks
    """
    print("[Layer 5] 🌐 Local DB empty. Initiating Web Fallback Search...")

    if not DDGS_AVAILABLE:
        print("[Layer 5] ⚠️  duckduckgo-search not installed. Skipping.")
        print("          Run: pip install duckduckgo-search")
        return []

    try:
        # ── PII Scrubber ──
        # Replace personal identifiers with category labels
        # to preserve search query structure without leaking data
        import re
        scrubbed_query = query

        # Replace email addresses with EMAIL label
        scrubbed_query = re.sub(r'[\w.+-]+@[\w-]+\.[a-z]+', '[EMAIL]', scrubbed_query)

        # Replace phone numbers with PHONE label
        scrubbed_query = re.sub(r'\b\d{10}\b|\b\+91\d{10}\b', '[PHONE]', scrubbed_query)

        # Replace Aadhaar-like numbers (12 digits) with ID label
        scrubbed_query = re.sub(r'\b\d{12}\b', '[ID_NUMBER]', scrubbed_query)

        # Replace individual person names (capitalized words not in legal vocab)
        LEGAL_CAPS = {
            "Industrial", "Disputes", "Act", "Supreme", "Court",
            "High", "Section", "Article", "India", "Indian",
            "Payment", "Wages", "Motor", "Vehicles", "Criminal",
            "Procedure", "Evidence", "Penal", "Code", "Hindu",
            "Marriage", "Negotiable", "Instruments", "Civil",
            "Constitution", "Labour", "Consumer", "Protection"
        }
        scrubbed_query = re.sub(
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b',
            lambda m: m.group(0) if any(
                word in LEGAL_CAPS for word in m.group(0).split()
            ) else '[NAME]',
            scrubbed_query
        ).strip()

        # Clean up extra spaces from removed tokens
        scrubbed_query = re.sub(r'\s+', ' ', scrubbed_query).strip()

        if scrubbed_query != query:
            print(f"[Layer 5] 🔒 PII scrubbed from query before web search")

        # Target Indian legal sources via site: operators (pre-filter, not post-filter)
        # DuckDuckGo supports site: operators natively — results come pre-filtered
        DOMAIN_OPERATORS = [
            "site:indiankanoon.org",
            "site:indiacode.nic.in",
            "site:livelaw.in",
            "site:scconline.com",
            "site:barandbench.com",
        ]
        site_filter = " OR ".join(DOMAIN_OPERATORS)
        search_query = f"({site_filter}) {scrubbed_query}"
        print(f"[Layer 5] Searching: {search_query[:100]}...")

        results = DDGS().text(search_query, max_results=5)

        if not results:
            print("[Layer 5] No web results found.")
            return []

        # Post-filter to ensure only Indian legal domains pass through
        INDIAN_DOMAINS = ("indiankanoon.org", "indiacode.nic.in", "scconline.com",
                          "manupatra.com", "barandbench.com", "livelaw.in",
                          "supremecourtcaselaw.com")
        filtered = []
        for r in results:
            href = r.get("href", "").lower()
            if any(d in href for d in INDIAN_DOMAINS):
                filtered.append(r)
        results = filtered[:3] if filtered else results[:3]

        if not results:
            return []

        # Format results to match ChromaDB chunk structure exactly
        # Layer 3 receives these as if they came from local database
        # "act_name: Live Web Search" signals Layer 3 this is web data
        mock_chunks = []
        for i, res in enumerate(results, 1):
            href = res.get('href', '')
            # Classify source authority: indiankanoon/indiacode = primary, blogs/news = commentary
            is_primary = any(d in href.lower() for d in ["indiankanoon.org", "indiacode.nic.in", "scconline.com"])
            source_type = "primary" if is_primary else "commentary"
            # Score by source authority — primary sources more trustworthy
            SCORE_MAP = {"primary": 0.72, "commentary": 0.55}
            mock_chunks.append({
                "act_name":       "Live Web Search",
                "section_number": f"Source {i}",
                "is_repealed":    False,
                "law_type":       "Web Result",
                "source_type":    source_type,
                "content": (
                    f"TITLE: {res.get('title', '')}\n"
                    f"SUMMARY: {res.get('body', '')}\n"
                    f"SOURCE: {href}"
                ),
                "relevance_score": SCORE_MAP.get(source_type, 0.55)
            })

        print(f"[Layer 5] ✅ Web fallback found {len(mock_chunks)} results.")
        return mock_chunks

    except Exception as e:
        print(f"[Layer 5] ⚠️  Web fallback failed: {e}")
        return []


def run_database_update():
    """
    Executes scraper + chunker to refresh ChromaDB.
    Called by APScheduler every 30 days.
    Uses subprocess so it runs in separate process
    and never blocks the main pipeline.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{timestamp}] 🔄 SCHEDULED DB UPDATE STARTING...")

    try:
        # Step 1: Run scraper
        print("  → Running 01_scraper.py...")
        subprocess.run(
            ["python", SCRAPER],
            check=True,
            cwd=REPO_DIR
        )
        print("  → Scraper complete.")

        # Step 2: Run chunker and embedder
        print("  → Running 02_chunk_and_embed.py...")
        subprocess.run(
            ["python", CHUNKER],
            check=True,
            cwd=REPO_DIR
        )
        print("  → Chunker complete.")

        done_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{done_time}] ✅ DATABASE UPDATE COMPLETE.\n")

    except subprocess.CalledProcessError as e:
        print(f"🚨 UPDATE FAILED: Script crashed. Error: {e}")

    except FileNotFoundError as e:
        print(f"🚨 UPDATE FAILED: Script file not found. Error: {e}")
        print(f"   Expected scraper at: {SCRAPER}")
        print(f"   Expected chunker at: {CHUNKER}")

    except Exception as e:
        print(f"🚨 UPDATE FAILED: Unknown error: {e}")


def start_auto_updater():
    """
    Starts the APScheduler background job.
    Call this once when FastAPI server starts.

    Returns:
        scheduler instance (call scheduler.shutdown() to stop)

    Usage in FastAPI main.py:
        from layer5_external import start_auto_updater
        scheduler = start_auto_updater()

        @app.on_event("shutdown")
        def shutdown_scheduler():
            scheduler.shutdown()
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_database_update,
            trigger   = 'interval',
            days      = 30,
            id        = 'monthly_law_update',
            replace_existing = True
        )
        scheduler.start()

        next_run = datetime.now().strftime('%Y-%m-%d')
        print(f"⏳ Auto-updater started. DB will refresh every 30 days.")
        print(f"   Next update: 30 days from {next_run}")

        return scheduler

    except ImportError:
        print("⚠️  APScheduler not installed. Auto-updater disabled.")
        print("   Install with: pip install apscheduler")
        return None

    except Exception as e:
        print(f"⚠️  Auto-updater failed to start: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("-" * 55)
    print("SaulGPT — Layer 5 External Tools Test")
    print("-" * 55)

    # Test IndiaKanoon fetcher
    print("\nTest: Fetching case law for wage dispute...")
    result = fetch_case_law(
        query       = "employer unpaid wages legal remedy",
        act_name    = "Payment of Wages Act",
        section_num = "15"
    )

    if result:
        print("\n" + result)
    else:
        print("No results (offline or blocked)")

    print("\n" + "=" * 55)
    print("Layer 5 External Tools test complete.")