import os
import json
import logging
import time
from tqdm import tqdm
from scraper.engine import LegalScraperEngine

# --- LOGGING SETUP ---
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "pipeline.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "scraper", "config.json")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_scraper(limit=None):
    engine = LegalScraperEngine()
    acts = load_config()
    
    if limit:
        acts = acts[:limit]

    print(f"Starting SaulGPT Production Scraper...")
    
    for act in tqdm(acts, desc="Scraping Acts"):
        name = act["name"]
        year = act["year"]
        filename = f"{name.lower().replace(' ', '_')}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Load existing for change detection
        existing_data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading existing data for {name}: {e}")

        sections, source = engine.scrape_act(name)
        
        if not sections:
            logger.error(f"Failed to scrape {name} from any source.")
            continue
            
        # Change Detection & Update
        result = {
            "act_name": name,
            "year": year,
            "source": source,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sections": sections
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Saved {len(sections)} sections for {name} from {source}")

def verify_data():
    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")]
    total_sections = 0
    for f in files:
        try:
            with open(os.path.join(OUTPUT_DIR, f), 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                total_sections += len(data.get("sections", []))
        except: pass
    
    print("\nScraping complete")
    print(f"Acts downloaded: {len(files)}")
    print(f"Total sections collected: {total_sections}")

if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_scraper(limit=limit)
    verify_data()
