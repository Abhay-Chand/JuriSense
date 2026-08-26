"""
Discovery Agent - Phase 1 of the 3-Phase Pipeline
===================================================
Structured 3-turn discovery: Story → Evidence → Outcome.
Each turn has a fixed objective; skipped if fields are already populated.
Outputs structured discovery_profile JSON for Phase 2.
"""

import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.llm_client import get_discovery_llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.discovery import DISCOVERY_SYSTEM_PROMPT
from typing import Optional, Dict, Any

# Turn objectives injected into the prompt based on turn index
_TURN_OBJECTIVES = {
    0: {
        "label": "Story & Legal Anchor",
        "summary": "Acknowledge the situation, anchor it in the relevant area of law, then ask the user to describe what happened. Do NOT ask about evidence or outcome yet.",
    },
    1: {
        "label": "Evidence & Timeline",
        "summary": "Ask about documentary proof and clarify the exact timeline. If both evidence_quality and timeline.value are already populated in the profile, skip questions and set discovery_complete=true.",
    },
    2: {
        "label": "Outcome & Priority",
        "summary": "Ask what the user wants and what matters most. This is the FINAL turn — set discovery_complete=true regardless. Only ask about fields that are still empty.",
    },
}


class DiscoveryAgent:
    """
    Discovery Agent - Phase 1
    Structured 3-turn investigation with adaptive skip logic.
    """

    def __init__(self):
        self.llm = get_discovery_llm()
        self.name = "Discovery"

    async def run(self, query: str, existing_profile: dict = None, discovery_turn: int = 0) -> Dict[str, Any]:
        """
        Run Discovery on a query.

        Args:
            query: The user's current message
            existing_profile: Existing discovery profile from previous turns
            discovery_turn: Which turn this is (0-indexed)

        Returns:
            Dict with response, discovery_complete, discovery_profile
        """
        prompt = DISCOVERY_SYSTEM_PROMPT

        if existing_profile and any(existing_profile.values()):
            prompt += f"\n\n## Previous Context\n{json.dumps(existing_profile, indent=2)}"

        turn_num = min(discovery_turn, 2)  # clamp to 0-2
        turn_obj = _TURN_OBJECTIVES[turn_num]
        prompt += (
            f"\n\n## Current Turn\n"
            f"Turn {turn_num + 1} of 3\n"
            f"Objective: {turn_obj['label']}\n"
            f"{turn_obj['summary']}"
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ]

        try:
            result = await self.llm.ainvoke(messages)
            content = result.content.strip()

            parsed = _extract_json(content)
            if parsed is None:
                return {
                    "skip_discovery": False,
                    "discovery_complete": False,
                    "response": content[:500] if content else "Could you tell me more about what happened?",
                    "discovery_profile": {},
                    "extracted_fields": {},
                    "_parse_error": "Could not extract JSON from LLM output"
                }

            parsed.setdefault("skip_discovery", False)
            parsed.setdefault("discovery_complete", False)
            parsed.setdefault("discovery_profile", {})
            parsed.setdefault("extracted_fields", {})
            parsed.setdefault("response", "Could you tell me more about what happened?")

            return parsed

        except Exception as e:
            return {
                "skip_discovery": False,
                "discovery_complete": False,
                "response": "I understand you're facing a legal issue. Could you tell me a bit more about what happened and what outcome you're looking for?",
                "discovery_profile": {},
                "extracted_fields": {},
                "_error": str(e)
            }


def _extract_json(content: str) -> Optional[Dict]:
    """Robust JSON extraction: pure JSON -> markdown code block -> markdown key-value pairs."""
    # 1. Try direct JSON parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. Try markdown code block
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Try extracting key-value pairs from markdown
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
