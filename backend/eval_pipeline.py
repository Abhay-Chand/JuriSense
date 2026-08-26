"""
SaulGPT — Automated RAG & Hallucination Evaluation
===================================================
Tests ChromaDB retrieval accuracy, LLM response grounding,
and anti-hallucination against a gold-standard evaluation set.

Usage:
    & ".venv\Scripts\python.exe" eval_pipeline.py
    & ".venv\Scripts\python.exe" eval_pipeline.py --verbose
"""

import sys
import os
import json
import time
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layer1_understanding import analyze_query
from layer2_retrieval import retrieve_with_hybrid_logic
from layer3_reasoning import generate_legal_response
from layer4_validation import validate_legal_response

# ── Gold-standard evaluation dataset ──
EVAL_DATASET = [
    {
        "query": "Can a contract be cancelled solely because the consideration is grossly inadequate?",
        "mode": "knowledge",
        "expected_keywords": [
            "Specific Relief Act", "1963", "2018 Amendment",
            "not a defense", "grossly inadequate"
        ],
        "forbidden_keywords": [
            "discretionary power", "1877 Act", "Section 28"
        ],
        "min_confidence": 0.60,
        "description": "Contract law - consideration inadequacy",
    },
    {
        "query": "What is the limitation period to file a suit for breach of a rental agreement in Chennai?",
        "mode": "knowledge",
        "expected_keywords": [
            "3 years", "Limitation Act", "1963", "Article 55"
        ],
        "forbidden_keywords": [
            "1 year", "5 years", "reasonable time", "12 years"
        ],
        "min_confidence": 0.60,
        "description": "Limitation - breach of contract",
    },
    {
        "query": "My employer hasn't paid my salary for 3 months. What are my legal options?",
        "mode": "analysis",
        "expected_keywords": [
            "Payment of Wages Act", "notice", "legal notice",
            "labour commissioner"
        ],
        "forbidden_keywords": [
            "contract for service", "independent contractor"
        ],
        "min_confidence": 0.60,
        "description": "Employment - unpaid wages",
    },
    {
        "query": "What is Section 138 of the Negotiable Instruments Act?",
        "mode": "knowledge",
        "expected_keywords": [
            "cheque", "dishonour", "negotiable", "bounce",
            "notice within 30 days"
        ],
        "forbidden_keywords": [
            "Indian Easements Act", "easement"
        ],
        "min_confidence": 0.60,
        "description": "Cheque bounce - Section 138 NIA",
    },
    {
        "query": "Can I file a case under Section 420 IPC for cheating of Rs 5 Lakhs?",
        "mode": "knowledge",
        "expected_keywords": [
            "BNS", "Section 318", "cheating", "Bharatiya Nyaya Sanhita"
        ],
        "forbidden_keywords": [
            "7 years", "Section 420 IPC"
        ],
        "min_confidence": 0.50,
        "description": "IPC 420 → BNS 318 mapping",
    },
    {
        "query": "How to file an FIR in India?",
        "mode": "pathfinder",
        "expected_keywords": [
            "FIR", "police station", "Zero FIR", "Section 173"
        ],
        "forbidden_keywords": [
            "Section 156 IPC"
        ],
        "min_confidence": 0.50,
        "description": "FIR filing procedure",
    },
    {
        "query": "My landlord entered my apartment without notice. What are my rights?",
        "mode": "analysis",
        "expected_keywords": [
            "notice", "tenant", "rental", "landlord"
        ],
        "forbidden_keywords": [
            "Section 420", "murder"
        ],
        "min_confidence": 0.50,
        "description": "Rental - landlord entry without notice",
    },
    {
        "query": "What are the grounds for divorce under Hindu Marriage Act?",
        "mode": "knowledge",
        "expected_keywords": [
            "Hindu Marriage Act", "1955", "Section 13",
            "cruelty", "desertion", "adultery"
        ],
        "forbidden_keywords": [
            "dissolution of marriage"
        ],
        "min_confidence": 0.60,
        "description": "Divorce - Hindu Marriage Act grounds",
    },
]


def test_rag_accuracy(case: dict, verbose: bool = False) -> dict:
    """Run a single evaluation case through the pipeline and score it."""
    query = case["query"]
    mode = case["mode"]
    result = {
        "query": query,
        "description": case["description"],
        "passed": True,
        "checks": {},
        "errors": [],
        "elapsed": 0,
    }

    start = time.time()

    try:
        # Step 1: Layer 1 — Understanding
        layer1 = analyze_query(query, conversation_history=[])
        if not layer1:
            result["passed"] = False
            result["errors"].append("Layer 1 returned empty result")
            return result

        # Step 2: Layer 2 — Retrieval
        retrieved = retrieve_with_hybrid_logic(layer1)
        laws_retrieved = len(retrieved) if retrieved else 0
        result["laws_retrieved"] = laws_retrieved

        if verbose:
            print(f"  Laws retrieved: {laws_retrieved}")

        # Step 3: Layer 3 — Reasoning
        response = generate_legal_response(layer1, retrieved or [], mode)

        if not response:
            result["passed"] = False
            result["errors"].append("Layer 3 returned empty response")
            return result

        result["response_preview"] = response[:150]

        # Step 4: Layer 4 — Validation
        validated = validate_legal_response(response, retrieved or [])
        result["confidence"] = validated.get("confidence_score", 0)
        result["is_hallucinating"] = validated.get("is_hallucinating", False)

        if verbose:
            print(f"  Confidence: {result['confidence']:.2f}")
            print(f"  Hallucination: {result['is_hallucinating']}")

        # ── CHECK 1: Confidence score threshold ──
        min_conf = case.get("min_confidence", 0.60)
        conf_ok = result["confidence"] >= min_conf
        result["checks"]["confidence"] = {
            "passed": conf_ok,
            "value": result["confidence"],
            "threshold": min_conf,
        }
        if not conf_ok:
            result["passed"] = False
            result["errors"].append(
                f"Confidence {result['confidence']:.2f} < threshold {min_conf}"
            )

        # ── CHECK 2: Expected keywords present ──
        missing = []
        for kw in case.get("expected_keywords", []):
            if kw.lower() not in response.lower():
                missing.append(kw)
        result["checks"]["expected_keywords"] = {
            "passed": len(missing) == 0,
            "missing": missing,
            "total": len(case.get("expected_keywords", [])),
        }
        if missing:
            result["passed"] = False
            result["errors"].append(f"Missing keywords: {missing}")

        # ── CHECK 3: Forbidden keywords absent ──
        found_bad = []
        for kw in case.get("forbidden_keywords", []):
            if kw.lower() in response.lower():
                found_bad.append(kw)
        result["checks"]["forbidden_keywords"] = {
            "passed": len(found_bad) == 0,
            "found": found_bad,
        }
        if found_bad:
            result["passed"] = False
            result["errors"].append(f"Forbidden keywords found: {found_bad}")

        # ── CHECK 4: Hallucination flag ──
        if result["is_hallucinating"]:
            result["checks"]["hallucination"] = {
                "passed": False,
                "note": "Layer 4 flagged potential hallucination",
            }
            result["passed"] = False
            result["errors"].append("Layer 4 flagged hallucination")
        else:
            result["checks"]["hallucination"] = {"passed": True}

    except Exception as e:
        result["passed"] = False
        result["errors"].append(f"Exception: {str(e)}")

    result["elapsed"] = round(time.time() - start, 2)
    return result


def run_eval_suite(verbose: bool = False) -> dict:
    """Run all evaluation cases and return summary."""
    print(f"\n{'='*60}")
    print(f"  SAULGPT — RAG EVALUATION SUITE")
    print(f"  {len(EVAL_DATASET)} test cases")
    print(f"{'='*60}\n")

    results = []
    passed = 0
    failed = 0

    for i, case in enumerate(EVAL_DATASET):
        desc = case["description"]
        print(f"[{i+1}/{len(EVAL_DATASET)}] {desc}...", end=" " if not verbose else "\n")
        sys.stdout.flush()

        result = test_rag_accuracy(case, verbose=verbose)

        if result["passed"]:
            passed += 1
            if not verbose:
                print(f"✅ PASS ({result['elapsed']}s, conf={result.get('confidence', 0):.2f})")
        else:
            failed += 1
            if not verbose:
                print(f"❌ FAIL ({result['elapsed']}s)")
            if verbose:
                for err in result["errors"]:
                    print(f"     ⚠️  {err}")

        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{len(EVAL_DATASET)} passed, {failed} failed")
    print(f"{'='*60}\n")

    # Detailed failure report
    if failed > 0:
        print("FAILURE DETAILS:")
        for r in results:
            if not r["passed"]:
                print(f"\n  ❌ [{r['description']}]")
                print(f"     Query: {r['query'][:80]}...")
                print(f"     Response: {r.get('response_preview', 'N/A')}...")
                for err in r["errors"]:
                    print(f"     ⚠️  {err}")

    return {
        "total": len(EVAL_DATASET),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    result = run_eval_suite(verbose=verbose)

    # Exit code: 0 if all passed, 1 if any failed
    sys.exit(0 if result["failed"] == 0 else 1)
