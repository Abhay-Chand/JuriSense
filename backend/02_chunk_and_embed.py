"""
SaulGPT Legal RAG Pipeline - Module 2: Chunk and Embed

Reads all scraped JSON files from raw_data/
Chunks each section intelligently
Embeds using sentence-transformers
Stores in ChromaDB vector database

FIX: Universal key detector handles ALL key naming variations
     across all 10 JSON files — no more 0 chunks

Run:
    python legal_pipeline/02_chunk_and_embed.py

Output:
    your_repo/vector_db/  <- ChromaDB persistent storage
"""

import os
import json
from glob import glob
from tqdm import tqdm
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb

# ─────────────────────────────────────────────────────────────
# ABSOLUTE PATHS
# Based on this file's location — works from any directory
# __file__ = your_repo/legal_pipeline/02_chunk_and_embed.py
# BASE_DIR = your_repo/legal_pipeline/
# REPO_DIR = your_repo/
# ─────────────────────────────────────────────────────────────

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
REPO_DIR       = os.path.dirname(BASE_DIR)

# your_repo/data/raw_data/ — where your JSON files are
RAW_DATA_DIR   = os.path.join(REPO_DIR, "data", "raw_data")

# your_repo/data/vector_db/ — where ChromaDB will be saved
# layer2_retrieval.py must use this EXACT same path
VECTOR_DB_PATH = os.path.join(REPO_DIR, "data", "vector_db")

# Collection name — layer2_retrieval.py must use same name
COLLECTION_NAME = "saulgpt_indian_laws"

# Embedding model — layer2_retrieval.py must use same model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking config
CHUNK_SIZE    = 1200
CHUNK_OVERLAP = 150

# ─────────────────────────────────────────────────────────────
# ALL POSSIBLE KEY NAMES ACROSS YOUR 10 JSON FILES
#
# WHY THIS FIX:
# CPC uses:  section, title, description   → worked
# CRPC uses: different keys                → stored 0
# HMA uses:  different keys                → stored 0
# IPC uses:  different keys                → stored 0
#
# Solution: try ALL possible key names
# Return first one that has a value
# ─────────────────────────────────────────────────────────────

# Every possible key name for section number
# CONFIRMED keys from your actual 10 JSON files:
# CPC:  section, title, description
# CRPC: section, section_title, section_desc
# HMA:  section, section_title, section_desc
# IEA:  section, section_title, section_desc
# NIA:  section, section_title, section_desc
# IPC:  Section (capital S!), section_title, section_desc

SEC_NUM_KEYS = [
    'section',       # CPC, CRPC, HMA, IEA, NIA
    'Section',       # IPC uses capital S
    'number', 'section_number', 'sec_no',
    'sec_num', 'sectionNumber', 'id', 'no', 'clause',
    'article_number', 'article_no', 'sec', 'section_no',
    'serial_no', 'sr_no', 'order'
]

# Every possible key name for section title/heading
TITLE_KEYS = [
    'section_title', # CRPC, HMA, IEA, NIA, IPC
    'title',         # CPC, Constitution
    'name', 'heading', 'sectionTitle', 'section_name',
    'caption', 'subject', 'head', 'section_heading',
    'header', 'short_title', 'marginal_note', 'chapter_title'
]

# Every possible key name for section text content
TEXT_KEYS = [
    'section_desc',  # CRPC, HMA, IEA, NIA, IPC <- WAS MISSING
    'description',   # CPC
    'text', 'content', 'body', 'section_text',
    'sectionText', 'provision', 'details', 'matter',
    'paragraph', 'value', 'data', 'detail',
    'section_content', 'full_text', 'act_text',
    'legal_text', 'section_body', 'sub_section',
    'clause_text', 'enactment', 'statutory_text'
]


# ─────────────────────────────────────────────────────────────
# UNIVERSAL FIELD EXTRACTOR
# ─────────────────────────────────────────────────────────────

def extract_field(item: dict, keys: list) -> str:
    """
    Tries multiple key names and returns first non-empty value.
    Handles all naming variations across your JSON files.

    Args:
        item: single section dict from JSON
        keys: list of candidate key names to try in order

    Returns:
        string value of first matching key, or empty string

    Example:
        extract_field(
            {"sec_no": "302", "heading": "Murder"},
            ['section', 'number', 'sec_no']
        )
        -> "302"
    """
    for key in keys:
        val = item.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ''


# ─────────────────────────────────────────────────────────────
# DEBUG HELPER
# Prints actual keys found in a JSON file
# Helps diagnose 0 chunk issues
# ─────────────────────────────────────────────────────────────

def debug_json_structure(data, filename: str):
    """
    Prints the actual key names found in a JSON file.
    Useful for diagnosing why a file stores 0 chunks.

    Args:
        data: parsed JSON content
        filename: name of the file for display
    """
    print(f"\n  [DEBUG] {filename} structure:")
    if isinstance(data, list):
        print(f"  Type: List of {len(data)} items")
        if data and isinstance(data[0], dict):
            print(f"  First item keys: {list(data[0].keys())}")
            # Show sample values to understand content
            for k, v in list(data[0].items())[:5]:
                preview = str(v)[:60].replace('\n', ' ')
                print(f"    '{k}': '{preview}'")
    elif isinstance(data, dict):
        print(f"  Type: Dict with keys: {list(data.keys())}")
        # Show nested structure
        for k, v in list(data.items())[:3]:
            if isinstance(v, list) and v:
                print(f"  '{k}': list of {len(v)}, first item keys: "
                      f"{list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")
            else:
                print(f"  '{k}': {type(v)}")


# ─────────────────────────────────────────────────────────────
# UNIVERSAL SECTION ITERATOR
# Handles ALL JSON structures across your 10 files
# ─────────────────────────────────────────────────────────────

def iter_sections_from_json(data, act_name_hint=None, debug=False):
    """
    Yields (section_number, section_title, section_text)
    for every section in a JSON file.

    Uses universal key detector — tries all possible key names
    so every JSON file works regardless of naming convention.

    Args:
        data: parsed JSON (list or dict)
        act_name_hint: fallback act name from filename
        debug: if True prints key names found in file

    Yields:
        (section_number, title, text) tuples
        Only yields sections that have non-empty text
    """

    if debug:
        debug_json_structure(data, act_name_hint)

    # ── Structure 1: List of sections ──
    # Used by: CPC, CRPC, HMA, IEA, IPC, MVA, NIA etc
    # [{"section": 1, "title": "...", "description": "..."}, ...]
    if isinstance(data, list):
        count = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            sec_num = extract_field(item, SEC_NUM_KEYS) or '?'
            title   = extract_field(item, TITLE_KEYS)
            text    = extract_field(item, TEXT_KEYS)
            if text:
                count += 1
                yield sec_num, title, text
        if debug:
            print(f"  [DEBUG] List structure yielded {count} sections")
        return

    # ── Structure 2-5: Dict ──
    if not isinstance(data, dict):
        print(f"  WARNING: Unknown structure in {act_name_hint} — skipping")
        return

    # ── Structure 2: Constitution (parts > articles) ──
    # {"parts": [{"name": "PART I", "articles": [...]}]}
    if 'parts' in data:
        count = 0
        for part in data['parts']:
            part_name = part.get('name', '')
            articles  = part.get('articles', [])
            for article in articles:
                if not isinstance(article, dict):
                    continue
                sec_num    = extract_field(article, SEC_NUM_KEYS) or '?'
                title      = extract_field(article, TITLE_KEYS)
                text       = extract_field(article, TEXT_KEYS)
                full_title = f"{part_name} - {title}" if part_name else title
                if text:
                    count += 1
                    yield sec_num, full_title.strip(), text.strip()
        if debug:
            print(f"  [DEBUG] Parts structure yielded {count} sections")
        return

    # ── Structure 3: Flat articles ──
    # {"articles": [...]}
    if 'articles' in data:
        count = 0
        for article in data['articles']:
            if not isinstance(article, dict):
                continue
            sec_num = extract_field(article, SEC_NUM_KEYS) or '?'
            title   = extract_field(article, TITLE_KEYS)
            text    = extract_field(article, TEXT_KEYS)
            if text:
                count += 1
                yield sec_num, title, text
        if debug:
            print(f"  [DEBUG] Articles structure yielded {count} sections")
        return

    # ── Structure 4: Flat sections ──
    # {"sections": [...]}
    if 'sections' in data:
        count = 0
        for section in data['sections']:
            if not isinstance(section, dict):
                continue
            sec_num = extract_field(section, SEC_NUM_KEYS) or '?'
            title   = extract_field(section, TITLE_KEYS)
            text    = extract_field(section, TEXT_KEYS)
            if text:
                count += 1
                yield sec_num, title, text
        if debug:
            print(f"  [DEBUG] Sections structure yielded {count} sections")
        return

    # ── Structure 5: Act wrapper dict ──
    # {"act_name": "...", "data": [...]} or similar
    # Try to find any list value inside the dict
    for key, val in data.items():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            count = 0
            if debug:
                print(f"  [DEBUG] Trying nested list under key '{key}'")
            for item in val:
                sec_num = extract_field(item, SEC_NUM_KEYS) or '?'
                title   = extract_field(item, TITLE_KEYS)
                text    = extract_field(item, TEXT_KEYS)
                if text:
                    count += 1
                    yield sec_num, title, text
            if count > 0:
                if debug:
                    print(f"  [DEBUG] Found {count} sections under '{key}'")
                return

    print(f"  WARNING: Could not find sections in {act_name_hint}")
    print(f"  Run with debug=True to see structure")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():

    # Load embedding model
    print("Loading embedding model...")
    embedder = SentenceTransformer(EMBEDDING_MODEL)
    print(f"Model loaded: {EMBEDDING_MODEL}\n")

    # Connect to ChromaDB
    print("Initializing ChromaDB...")
    client     = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    print(f"Collection ready: {COLLECTION_NAME}\n")

    # Find all JSON files
    json_files = glob(os.path.join(RAW_DATA_DIR, '*.json'))
    print(f"Found {len(json_files)} JSON files in {RAW_DATA_DIR}/\n")

    if not json_files:
        print(f"ERROR: No JSON files found in {RAW_DATA_DIR}/")
        print("Check that your JSON files are in your_repo/raw_data/")
        return

    # Text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = CHUNK_SIZE,
        chunk_overlap = CHUNK_OVERLAP,
        separators    = ["\n\n", "Section ", "SECTION ", "Sec. ", "sec. "]
    )

    total_chunks  = 0
    zero_files    = []

    for json_path in tqdm(json_files, desc="Processing acts"):

        filename = os.path.basename(json_path)
        act_name = os.path.splitext(filename)[0]

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"\nError reading {filename}: {e}")
            continue

        # Get act title from JSON or use filename
        if isinstance(data, dict):
            act_title = (
                data.get('title') or
                data.get('act_name') or
                data.get('name') or
                act_name
            )
        else:
            act_title = act_name

        print(f"\nProcessing: {act_title}")
        chunk_count = 0

        for sec_num, sec_title, sec_text in iter_sections_from_json(
            data,
            act_name_hint=act_title,
            debug=False       # set True to see key names for debugging
        ):
            if not sec_text.strip():
                continue

            # Split into chunks
            chunks = splitter.split_text(sec_text)

            for chunk in chunks:
                # Prepend lineage header
                # Bridges plain language queries to formal legal text
                prepended = (
                    f"[Act: {act_title}] "
                    f"[Section {sec_num}: {sec_title}].\n"
                    f"{chunk}"
                )

                # Generate embedding
                embedding = embedder.encode(prepended).tolist()

                # Metadata — keys must match layer2_retrieval.py
                metadata = {
                    "act_name":       act_title,
                    "section_number": sec_num,
                    "is_repealed":    False,
                    "law_type":       "Statute"
                }

                # Unique chunk ID
                chunk_id = f"{act_title}_{sec_num}_{chunk_count}"

                # Upsert into ChromaDB
                collection.upsert(
                    documents  = [prepended],
                    embeddings = [embedding],
                    metadatas  = [metadata],
                    ids        = [chunk_id]
                )

                chunk_count  += 1
                total_chunks += 1

        print(f"  Stored {chunk_count} chunks for {act_title}")

        # Track files that still store 0 chunks
        if chunk_count == 0:
            zero_files.append(filename)

    # Final summary
    print(f"\n{'='*55}")
    print("CHUNKING AND EMBEDDING COMPLETE")
    print(f"Total chunks stored : {total_chunks}")
    print(f"Vector DB path      : {VECTOR_DB_PATH}")
    print(f"Collection          : {COLLECTION_NAME}")
    print(f"Embedding model     : {EMBEDDING_MODEL}")

    # Diagnose any remaining 0 chunk files
    if zero_files:
        print(f"\nFiles with 0 chunks ({len(zero_files)}):")
        for f in zero_files:
            print(f"  - {f}")
        print("\nTo diagnose these files run:")
        print("  python legal_pipeline/diagnose_json.py")
        print("(see instructions below)")
    else:
        print("\nAll files processed successfully!")

    print(f"{'='*55}")
    print("\nReady to run layer2_retrieval.py")


# ─────────────────────────────────────────────────────────────
# DIAGNOSTIC HELPER
# If any file still shows 0 chunks after the fix
# run this to see its actual structure
# ─────────────────────────────────────────────────────────────

def diagnose_file(json_path: str):
    """
    Prints the actual key structure of any JSON file.
    Use this to diagnose files still showing 0 chunks.

    Usage:
        from chunk_and_embed import diagnose_file
        diagnose_file("raw_data/CRPC_from_db.json")
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    filename = os.path.basename(json_path)
    debug_json_structure(data, filename)
    print("\nIterating sections with debug=True:")
    count = 0
    for sec_num, title, text in iter_sections_from_json(
        data, act_name_hint=filename, debug=True
    ):
        count += 1
        if count <= 3:
            print(f"  Section {sec_num}: {title[:40]} | "
                  f"Text: {text[:60]}...")
    print(f"\nTotal sections found: {count}")


if __name__ == "__main__":
    main()
