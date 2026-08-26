"""
IRAC Agent — "Advocate Mode" Deep Legal Analysis
===================================================
Invoked intentionally by the user after Strategy phase.
Performs Layer 2 RAG retrieval + LLM generation in IRAC format.
Requires: GROQ_API_KEY, ChromaDB vector store at data/vector_db/
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.llm_client import get_triage_llm, get_drafter_llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.irac import IRAC_SYSTEM_PROMPT
from layer2_retrieval import retrieve_with_hybrid_logic
from typing import Dict, Any, Optional


class IRACAgent:
    """
    IRAC Advocate Mode — Intentional deep legal analysis.
    Not a hidden fallback. Invoked only when user explicitly requests it.
    """

    def __init__(self):
        self.llm = get_drafter_llm()
        self.name = "IRAC"

    async def run(self, query: str, discovery_profile: dict = None,
                  strategy_options: list = None) -> Dict[str, Any]:
        """
        Run IRAC analysis: RAG retrieval + structured generation.

        Args:
            query: The user's legal situation
            discovery_profile: Optional profile from Phase 1
            strategy_options: Optional options from Phase 2

        Returns:
            Dict with irac_output, citations, error if applicable
        """
        # Layer 2 RAG retrieval
        payload = {
            "search_optimized_query": query,
            "explicit_citations": [],
            "domain": "civil",
            "top_k": 8,
        }

        retrieved = []
        try:
            retrieved = await asyncio.to_thread(
                retrieve_with_hybrid_logic, payload
            )
        except Exception as e:
            retrieved = []

        # Build context from retrieved docs
        context_parts = []
        for doc in retrieved:
            act = doc.get("act_name", "Unknown Act")
            sec = doc.get("section_number", "")
            content = doc.get("content", "")[:600]
            repealed = doc.get("is_repealed", False)
            status = " [WARNING: REPEALED]" if repealed else ""
            context_parts.append(
                f"[{act}] Section {sec}{status}:\n{content}\n"
            )
        context = "\n---\n".join(context_parts) if context_parts else "No legal documents retrieved."

        # Build prompt
        profile_section = ""
        if discovery_profile and any(discovery_profile.values()):
            profile_section = f"\n\n## User Profile\n{json.dumps(discovery_profile, indent=2)}"

        options_section = ""
        if strategy_options:
            options_section = "\n\n## Available Legal Options\n"
            for opt in strategy_options:
                options_section += f"- **{opt.get('label', '')}**: {opt.get('description', '')}\n"

        prompt = (
            f"{IRAC_SYSTEM_PROMPT}\n\n"
            f"## User Query\n{query}"
            f"{profile_section}"
            f"{options_section}"
            f"\n\n## RETRIEVED LEGAL DOCUMENTS\n{context}"
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate a structured IRAC legal analysis of this situation based on the retrieved legal documents.")
        ]

        try:
            result = await self.llm.ainvoke(messages)
            content = result.content.strip()

            citations = []
            for doc in retrieved:
                citations.append({
                    "act_name": doc.get("act_name", ""),
                    "section_number": doc.get("section_number", ""),
                    "is_repealed": doc.get("is_repealed", False),
                    "relevance_score": doc.get("relevance_score", 0),
                })

            return {
                "response": content,
                "irac_output": content,
                "mode_used": "irac",
                "domain": "civil",
                "laws_retrieved": len(retrieved),
                "citations": citations,
                "graph_insights": [],
                "case_law_found": False,
                "is_hallucinating": False,
                "confidence_score": 0.8 if retrieved else 0.4,
                "flagged_citations": [],
                "repealed_warnings": [],
                "struck_down_warnings": [],
                "elapsed_seconds": 0,
                "interview_active": False,
            }

        except Exception as e:
            return {
                "response": "I encountered an error generating the IRAC analysis. Please try again or consult a lawyer.",
                "irac_output": None,
                "mode_used": "irac",
                "domain": "civil",
                "laws_retrieved": 0,
                "citations": [],
                "graph_insights": [],
                "case_law_found": False,
                "is_hallucinating": False,
                "confidence_score": 0.0,
                "flagged_citations": [],
                "repealed_warnings": [],
                "struck_down_warnings": [],
                "elapsed_seconds": 0,
                "_error": str(e),
                "interview_active": False,
            }
