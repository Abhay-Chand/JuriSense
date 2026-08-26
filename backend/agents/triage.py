"""
Triage Agent - Strategic Query Analysis
=======================================
Intercepts ALL queries before mode detection.
Uses TOWS reasoning to generate SWOT + strategic options.

v3 upgrades:
  - Limitation/jurisdiction gates
  - MSME/freelancer detection
  - Missing-variable intake loop
"""

import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .llm_client import triage, get_triage_llm, TRIAGE_MODEL
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from prompts.triage import TRIAGE_SYSTEM_PROMPT, TRIAGE_CLARIFY_PROMPT
from typing import Optional, Dict, Any


class TriageAgent:
    """
    Triage Agent - analyzes each incoming query to determine:
    1. Is the query clear enough? (pass_through)
    2. What role/goal can be inferred?
    3. What strategic options should be presented?
    4. Are all required variables collected? (intake loop)
    """

    def __init__(self):
        self.llm = triage
        self.name = "Triage"

    async def analyze(self, query: str, state: dict = None) -> Dict[str, Any]:
        """
        Analyze a query and return triage result.

        Args:
            query: The user's current message
            state: Existing triage state dict (None if new session)

        Returns:
            Dict with pass_through, swot, options, etc.
        """
        is_clarify = state and state.get("allow_explain") and query.lower().strip() in [
            "explain", "explain these", "tell me more", "what does this mean",
            "what are these options", "help", "help me choose"
        ]

        if is_clarify:
            return await self._explain_options(state)

        # Build prompt with context from existing state
        prompt = TRIAGE_SYSTEM_PROMPT
        context_lines = []

        if state:
            if state.get("is_triaged"):
                context_lines.append(f"Previous role: {state.get('role', 'unknown')}")
                context_lines.append(f"Previous goal: {state.get('goal', 'unknown')}")
                context_lines.append(f"Previous options shown: {state.get('options_shown', [])}")
                context_lines.append("The user is now sending a follow-up. Re-evaluate.")

            # Pass existing intake fields so LLM knows what's already collected
            intake = state.get("intake_fields", {})
            if intake:
                context_lines.append("Already known about this case:")
                for k, v in intake.items():
                    if v:
                        context_lines.append(f"  {k}: {v}")

            if context_lines:
                prompt += "\n\n## Existing Case Context\n" + "\n".join(context_lines)

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"User query: {query}")
        ]

        try:
            result = await self.llm.ainvoke(messages)
            content = result.content.strip()

            # Robust JSON extraction: try pure JSON, then markdown code block, then markdown key-value
            parsed = None
            # 1. Try direct JSON parse
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                pass

            # 2. Try markdown code block (```json ... ```)
            if parsed is None:
                m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
                if m:
                    try:
                        parsed = json.loads(m.group(1).strip())
                    except json.JSONDecodeError:
                        pass

            # 3. Try extracting key-value pairs from markdown (e.g. **pass_through:** false)
            if parsed is None:
                kv = {}
                for line in content.split('\n'):
                    line = line.strip().rstrip(',')
                    # Match patterns like **key:** value or **key:** "value"
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
                if kv.get("pass_through") is not None:
                    parsed = kv

            # 4. Final fallback to empty dict
            if parsed is None:
                parsed = {}

            # Validate required fields
            if "pass_through" not in parsed:
                parsed["pass_through"] = False
            if "is_intake_needed" not in parsed:
                parsed["is_intake_needed"] = False
            if "extracted_fields" not in parsed:
                parsed["extracted_fields"] = {}

            return parsed

        except Exception as e:
            return {
                "pass_through": True,
                "role": None,
                "suggested_mode": None,
                "clarifying_question": None,
                "swot_analysis": None,
                "options": None,
                "is_intake_needed": False,
                "extracted_fields": {},
                "limitation_warning": None,
                "jurisdiction_note": None,
                "allow_explanation_trigger": False,
                "_parse_error": str(e)
            }

    async def _explain_options(self, state: dict) -> Dict[str, Any]:
        """Generate plain-language explanation of previously-shown options."""
        role = state.get("role", "unknown")
        options = state.get("options_shown", [])
        opt_text = "\n".join(f"- {o.get('label', '?')}: {o.get('description', '')}" for o in options)

        messages = [
            SystemMessage(content="You are a helpful legal assistant. Explain options in simple terms."),
            HumanMessage(content=TRIAGE_CLARIFY_PROMPT.format(role=role, options=opt_text))
        ]

        try:
            result = await self.llm.ainvoke(messages)
            explanation = result.content.strip()
        except Exception:
            explanation = "I'm here to help you understand your options. Could you tell me more about your situation so I can guide you?"

        return {
            "pass_through": False,
            "role": role,
            "suggested_mode": None,
            "clarifying_question": explanation,
            "swot_analysis": None,
            "options": None,
            "is_intake_needed": False,
            "extracted_fields": {},
            "allow_explanation_trigger": False,
            "_is_explanation": True
        }
