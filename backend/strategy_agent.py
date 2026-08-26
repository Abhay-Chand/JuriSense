"""
Strategy Agent - Phase 2 of the 3-Phase Pipeline
===================================================
Generates SWOT analysis + strategic options filtered by discovery profile.
Uses Counsel Override to recommend suppressed options when objectively better.
"""

import json, re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.llm_client import get_triage_llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.strategy import STRATEGY_SYSTEM_PROMPT
from typing import Optional, Dict, Any


class StrategyAgent:
    """
    Strategy Agent - Phase 2
    Generates SWOT + filtered options based on Discovery Profile.
    """

    def __init__(self):
        self.llm = get_triage_llm()
        self.name = "Strategy"

    async def run(self, query: str, discovery_profile: dict) -> Dict[str, Any]:
        """
        Run Strategy analysis.

        Args:
            query: The original user query
            discovery_profile: The profile from Phase 1

        Returns:
            Dict with SWOT, options, limitation/jurisdiction
        """
        profile_json = json.dumps(discovery_profile, indent=2)
        prompt = f"{STRATEGY_SYSTEM_PROMPT}\n\n## Discovery Profile\n{profile_json}\n\n## Original Query\n{query}"

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the strategy based on this profile.")
        ]

        try:
            result = await self.llm.ainvoke(messages)
            content = result.content.strip()

            parsed = _extract_json(content)

            if parsed is None:
                return {
                    "response": content[:500] if content else "No response generated.",
                    "swot_analysis": None,
                    "options": [],
                    "limitation_warning": None,
                    "jurisdiction_note": None,
                    "allow_explanation_trigger": True,
                    "counsel_override": None,
                }

            parsed.setdefault("response", "Based on your situation, here are your strategic options.")
            parsed.setdefault("swot_analysis", None)
            parsed.setdefault("options", [])
            parsed.setdefault("limitation_warning", None)
            parsed.setdefault("jurisdiction_note", None)
            parsed.setdefault("allow_explanation_trigger", True)
            parsed.setdefault("counsel_override", None)

            # Validate and enforce: exactly 4 options with path_a..path_d IDs + route_to
            VALID_IDS = {"path_a", "path_b", "path_c", "path_d"}
            VALID_ROUTES = {"document", "pathfinder"}
            validated_options = []
            seen_ids = set()
            for opt in parsed.get("options", []):
                oid = opt.get("id", "")
                if oid not in VALID_IDS or oid in seen_ids:
                    continue  # skip duplicates, skip path_e etc.
                route = opt.get("route_to", "pathfinder")
                if route not in VALID_ROUTES:
                    route = "pathfinder"  # default safe
                validated_options.append({
                    "id": oid,
                    "label": opt.get("label", oid),
                    "description": opt.get("description", ""),
                    "route_to": route,
                    "reason": opt.get("reason", ""),
                })
                seen_ids.add(oid)

            # Pad missing IDs with universal catch-alls (NEVER assume a legal path)
            # These are context-independent safe recommendations that apply to ANY case.
            SAFE_DEFAULTS = {
                "path_a": ("Consult a Lawyer", "Get a professional legal opinion on your specific situation before proceeding.", "pathfinder"),
                "path_b": ("Gather All Evidence", "Collect documents, emails, contracts, and witness details to build your case.", "pathfinder"),
                "path_c": ("Send a Formal Notification", "Notify the opposing party in writing about your claim — creates a paper trail.", "pathfinder"),
                "path_d": ("Explore Mediation", "Consider a neutral third party to facilitate a conversation before formal action.", "pathfinder"),
            }
            for oid in sorted(VALID_IDS):
                if oid not in seen_ids:
                    label, desc, route = SAFE_DEFAULTS[oid]
                    validated_options.append({
                        "id": oid,
                        "label": label,
                        "description": desc,
                        "route_to": route,
                        "reason": "",
                    })

            parsed["options"] = validated_options

            return parsed

        except Exception as e:
            return {
                "response": "I've analyzed your situation. Here are your options.",
                "swot_analysis": None,
                "options": [
                    {"id": "path_a", "label": "Consult a Lawyer", "description": "Get a professional legal opinion on your specific situation before proceeding.", "route_to": "pathfinder", "reason": ""},
                    {"id": "path_b", "label": "Gather All Evidence", "description": "Collect documents, emails, contracts, and witness details to build your case.", "route_to": "pathfinder", "reason": ""},
                    {"id": "path_c", "label": "Send a Formal Notification", "description": "Notify the opposing party in writing about your claim.", "route_to": "pathfinder", "reason": ""},
                    {"id": "path_d", "label": "Explore Mediation", "description": "Consider a neutral third party to facilitate a conversation.", "route_to": "pathfinder", "reason": ""},
                ],
                "limitation_warning": None,
                "jurisdiction_note": None,
                "allow_explanation_trigger": True,
                "counsel_override": None,
                "_error": str(e)
            }


def _extract_json(content: str) -> Optional[Dict]:
    """Robust JSON extraction: pure JSON -> markdown code block -> markdown key-value pairs."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    kv = {}
    for line in content.split('\n'):
        line = line.strip().rstrip(',')
        m = re.match(r'\*{0,2}([a-z_]+)\*{0,2}:\s*(.+)$', line, re.IGNORECASE)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip().strip('"').strip("'")
            if val.lower() in ('true', 'false'):
                kv[key] = val.lower() == 'true'
            elif val.lower() == 'null':
                kv[key] = None
            elif val.startswith('{') or val.startswith('['):
                try:
                    kv[key] = json.loads(val)
                except json.JSONDecodeError:
                    kv[key] = val
            else:
                kv[key] = val
    if kv:
        return kv

    return None
