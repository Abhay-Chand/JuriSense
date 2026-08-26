"""
SAULGPT — LAYER 2: HYBRID RETRIEVAL
======================================
Techniques:
1. Semantic Search      — ChromaDB (all-MiniLM-L6-v2)
2. BM25 Keyword Search  — rank_bm25
3. Metadata Citation    — exact section_number filter
4. CrossEncoder         — ms-marco-MiniLM reranker
5. Deduplication        — content hash merge

Input:  UnderstandingResult dict from Layer 1
Output: Top k most relevant law section dicts

Run standalone to test:
    python layer2_retrieval.py

When used by pipeline_orchestrator.py:
    from layer2_retrieval import retrieve_with_hybrid_logic
    results = retrieve_with_hybrid_logic(layer1_payload)

IMPORTANT — matches 02_chunk_and_embed.py exactly:
    Embedding model : all-MiniLM-L6-v2
    Vector DB path  : vector_db
    Collection name : saulgpt_indian_laws
    Metadata keys   : act_name, section_number,
                      is_repealed, law_type
"""

import os
import re

from rank_bm25 import BM25Okapi

# ─────────────────────────────────────────────────────────────
# CONFIG — must match 02_chunk_and_embed.py exactly
# Changing any of these will cause zero results
# ─────────────────────────────────────────────────────────────

# Same model used in chunk_and_embed
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"

# Same absolute path logic used in 02_chunk_and_embed.py
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
REPO_DIR         = os.path.dirname(BASE_DIR)
VECTOR_DB_PATH = os.path.join(REPO_DIR, "data", "vector_db")

# Same collection name used in chunk_and_embed
COLLECTION_NAME  = "saulgpt_indian_laws"

# CrossEncoder reranker — scores results by true relevance
RERANKER_MODEL   = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Number of results to return after reranking
TOP_K            = 3

# ─────────────────────────────────────────────────────────────
# LAZY LOADING — heavy imports deferred until first query
# SentenceTransformer (~18s) + ChromaDB (~2s) loaded on demand
# ─────────────────────────────────────────────────────────────

_models_loaded = False
embedder = None
chroma_client = None
collection = None
reranker = None


def _ensure_models():
    """Load SentenceTransformer + ChromaDB on first call only."""
    global _models_loaded, embedder, chroma_client, collection, reranker
    if _models_loaded:
        return

    print("Loading retrieval models (first query)...")
    from sentence_transformers import SentenceTransformer, CrossEncoder
    import chromadb
    from chromadb.config import Settings

    embedder = SentenceTransformer(EMBEDDING_MODEL)

    chroma_client = chromadb.PersistentClient(
        path=VECTOR_DB_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

    reranker = CrossEncoder(RERANKER_MODEL)

    print(f"ChromaDB loaded. Collection: {COLLECTION_NAME}")
    print(f"Total chunks in DB: {collection.count()}\n")
    _models_loaded = True


# ─────────────────────────────────────────────────────────────
# BM25 INDEX BUILDER
# Loads all documents from ChromaDB and builds BM25 index
# ─────────────────────────────────────────────────────────────

def build_bm25_index(act_name_filter: str = None):
    """
    Builds BM25 keyword index from ChromaDB documents.
    Optionally filters by act_name for focused search.

    Args:
        act_name_filter: if provided filters docs to this act only
                         e.g. "Payment of Wages Act"

    Returns:
        bm25 index object,
        list of document texts,
        list of metadata dicts

    Example:
        bm25, docs, metas = build_bm25_index()
    """
    # Fetch all documents from collection
    # ChromaDB get() returns all stored chunks
    if act_name_filter:
        result = collection.get(
            where={"act_name": act_name_filter}
        )
    else:
        result = collection.get()

    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    if not documents:
        return None, [], []

    # Tokenize documents for BM25
    tokenized_corpus = [doc.lower().split() for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)

    return bm25, documents, metadatas


# ─────────────────────────────────────────────────────────────
# MAIN RETRIEVAL FUNCTION
# ─────────────────────────────────────────────────────────────

def retrieve_with_hybrid_logic(payload: dict, k: int = TOP_K) -> list:
    """
    Hybrid retrieval: semantic + BM25 + reranking.

    Takes Layer 1 output payload and returns
    top k most relevant law sections.

    Args:
        payload: dict from layer1_understanding.analyze_query()
                 must contain:
                 - search_optimized_query (str)
                 - explicit_citations (list)
                 - domain (str) [optional]

        k: number of results to return (default 8)

    Returns:
        list of result dicts each containing:
        content, act_name, section_number,
        is_repealed, law_type, relevance_score

    Example:
        results = retrieve_with_hybrid_logic({
            "search_optimized_query": "unpaid wages employer",
            "explicit_citations": ["SECTION 15"],
            "domain": "labour"
        })
    """

    _ensure_models()

    def _safe_top_k(value, default=TOP_K):
        """Guarantee a positive integer for ChromaDB n_results."""
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = default
        return value if value > 0 else default

    # Extract fields from Layer 1 payload
    semantic_query = payload.get("hyde_paragraph") or payload.get("search_optimized_query", "")
    keyword_query  = payload.get("keyword_synonyms") or payload.get("search_optimized_query", "")
    citations = payload.get("explicit_citations", [])
    top_k     = _safe_top_k(payload.get("top_k", k))

    print(f"\n[Layer 2] Semantic  : {semantic_query[:70]}...")
    print(f"[Layer 2] Keywords  : {keyword_query[:70]}...")
    print(f"[Layer 2] Citations : {citations}")
    print(f"[Layer 2] Top K     : {top_k}")

    # ── TECHNIQUE 1: Semantic Search via ChromaDB ──
    # Embeds query (uses HyDE paragraph) and finds nearest chunks by cosine similarity
    print("\n[1/3] Running semantic search (ChromaDB)...")

    query_embedding = embedder.encode(semantic_query).tolist()
    collection_count = collection.count()

    if collection_count <= 0:
        print("[Layer 2] WARNING: ChromaDB collection is empty.")
        return []

    # Check if we have an explicit citation to prioritize
    # If user mentioned "Section 15" filter ChromaDB by section_number
    # This gives exact match priority over semantic similarity
    semantic_results_raw = []

    if citations:
        # Extract number from citation e.g. "SECTION 15" → "15"
        sec_match = re.search(r'\d+', citations[0])
        if sec_match:
            sec_num = sec_match.group()
            print(f"[Layer 2] Citation filter: section_number = {sec_num}")
            try:
                # First try with citation filter
                filtered = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, collection_count),
                    where={"section_number": sec_num}
                )
                semantic_results_raw.extend(
                    zip(
                        filtered["documents"][0],
                        filtered["metadatas"][0]
                    )
                )
            except Exception as e:
                print(f"[Layer 2] Citation filter failed: {e} — running without filter")

    # Always run broad semantic search too
    # Combines with citation results for better coverage
    try:
        broad = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection_count)
        )
        for doc, meta in zip(broad["documents"][0], broad["metadatas"][0]):
            semantic_results_raw.append((doc, meta))
    except Exception as e:
        print(f"[Layer 2] ChromaDB query failed: {e}")
        return []

    print(f"[Layer 2] Semantic raw results: {len(semantic_results_raw)}")

    # ── TECHNIQUE 2: BM25 Keyword Search ──
    # Catches exact keyword matches semantic search may miss
    # Especially useful for exact section numbers and act names
    print("[2/3] Running BM25 keyword search...")

    bm25, bm25_docs, bm25_metas = build_bm25_index()
    bm25_results_raw = []

    if bm25 and bm25_docs:
        tokenized_query = keyword_query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        # Get top 20 scoring documents
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]

        for idx in top_indices:
            if scores[idx] > 0:
                bm25_results_raw.append((
                    bm25_docs[idx],
                    bm25_metas[idx],
                    scores[idx]
                ))

    print(f"[Layer 2] BM25 raw results: {len(bm25_results_raw)}")

    # ── COMBINE AND DEDUPLICATE ──
    # Merge semantic and BM25 results
    # Deduplicate by full content string — only merges exact duplicates
    combined = {}

    for doc, meta in semantic_results_raw:
        if doc not in combined:
            combined[doc] = {
                "content":        doc,
                "act_name":       meta.get("act_name", ""),
                "section_number": meta.get("section_number", ""),
                "is_repealed":    meta.get("is_repealed", False),
                "law_type":       meta.get("law_type", "Statute"),
            }

    for doc, meta, score in bm25_results_raw:
        if doc not in combined:
            combined[doc] = {
                "content":        doc,
                "act_name":       meta.get("act_name", ""),
                "section_number": meta.get("section_number", ""),
                "is_repealed":    meta.get("is_repealed", False),
                "law_type":       meta.get("law_type", "Statute"),
                "bm25_score":     score,
            }

    all_results = list(combined.values())
    print(f"[Layer 2] Combined unique results: {len(all_results)}")

    if not all_results:
        print("[Layer 2] WARNING: No results found in DB.")
        print("[Layer 2] Check: DB path, collection name, embedding model.")
        return []

    # ── TECHNIQUE 3: CrossEncoder Reranker ──
    # Scores every combined result against original query
    # Much more accurate than raw embedding similarity
    print("[3/3] Reranking with CrossEncoder...")

    pairs  = [(semantic_query, r["content"]) for r in all_results]
    scores = reranker.predict(pairs)

    # Sort by reranker score descending
    ranked = sorted(
        zip(scores, all_results),
        key=lambda x: x[0],
        reverse=True
    )

    # Build final top k results
    top_results = []
    for score, result in ranked[:top_k]:
        top_results.append({
            "content":         result["content"],
            "act_name":        result["act_name"],
            "section_number":  result["section_number"],
            "is_repealed":     result["is_repealed"],
            "law_type":        result["law_type"],
            "relevance_score": round(float(score), 4),
        })

    print(f"[Layer 2] Final top {len(top_results)} sections ready for Layer 3.\n")
    return top_results


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# Only runs when executed directly:
#   python layer2_retrieval.py
#
# Uses a simulated Layer 1 payload
# In production this payload comes from analyze_query()
# Test query covers labour law + explicit section citation
# which exercises all 3 retrieval techniques at once
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # Simulated Layer 1 output
    # In production: comes from layer1_understanding.analyze_query()
    test_payload = {
        "search_optimized_query": (
            "What are the legal conditions for a valid marriage regarding age and living spouses "
            "under Section 5 of the Hindu Marriage Act?"
        ),
        "domain":             "family",
        "explicit_citations": ["SECTION 5"],
        "is_ambiguous":       False,
    }

    print("-" * 55)
    print("SaulGPT — Layer 2 Hybrid Retrieval Test")
    print("-" * 55)

    results = retrieve_with_hybrid_logic(test_payload)

    print("\n" + "=" * 55)
    print("TOP RETRIEVED LEGAL SECTIONS")
    print("=" * 55)

    if not results:
        print("No results returned.")
        print("Troubleshooting:")
        print("  1. Run 02_chunk_and_embed.py first")
        print("  2. Check VECTOR_DB_PATH = 'vector_db'")
        print("  3. Check COLLECTION_NAME = 'saulgpt_indian_laws'")
    else:
        for i, result in enumerate(results, 1):
            print(f"\nRESULT {i}:")
            print(f"  ACT     : {result['act_name']}")
            print(f"  SECTION : {result['section_number']}")
            print(f"  SCORE   : {result['relevance_score']}")
            print(f"  REPEALED: {result['is_repealed']}")
            print(f"  CONTENT : {result['content'][:200]}...")

    print("\n" + "=" * 55)
    print("Layer 2 complete. Results ready for Layer 3.")
    print("=" * 55)
