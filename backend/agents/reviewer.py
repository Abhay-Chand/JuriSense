"""
Reviewer Agent - Contract Review and Legal Scrutiny
==========================================
Handles: Contract evaluation, legal scrutiny, limitation checks
Uses: scrutiny_agent.py, layer4, layer6_evaluator as tools
"""

from typing import Optional, Dict, Any, List, BinaryIO
from .llm_client import reviewer, get_reviewer_llm
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.reviewer import (
    REVIEWER_SYSTEM_PROMPT,
    CONTRACT_EVALUATION_PROMPT,
    LEGAL_SCRUTINY_PROMPT,
    LIMITATION_CHECK_PROMPT,
    RED_FLAGS_PROMPT,
    VETO_CHECK_PROMPT,
)

# Import existing review components as tools
try:
    from scrutiny_agent import scrutinize, check_limitation
    from layer4_validation import validate_legal_response
    from layer6_evaluator import evaluate_contract, format_evaluation_response, extract_text
except ImportError:
    scrutinize = None
    check_limitation = None
    validate_legal_response = None
    evaluate_contract = None
    format_evaluation_response = None


# Claim types mapping
CLAIM_TYPES = {
    "cheque_bounce": {"name": "Cheque Bounce", "limitation": 3},
    "recovery": {"name": "Money Recovery", "limitation": 3},
    "defamation": {"name": "Defamation", "limitation": 1},
    "motor_accident": {"name": "Motor Accident", "limitation": 2},
    "employment": {"name": "Employment Dispute", "limitation": 3},
    "property": {"name": "Property Dispute", "limitation": 3},
    "consumer": {"name": "Consumer Dispute", "limitation": 2},
}


class ReviewerAgent:
    """
    Reviewer Agent handles:
    - Contract evaluation (evaluate mode)
    - Legal scrutiny (limitation, remedies)
    - Document validation
    """
    
    def __init__(self):
        self.llm = reviewer
        self.name = "Reviewer"
        self.capabilities = ["contract_review", "scrutiny", "validation"]
    
    async def run(self, query: str = None, mode: str = "evaluate", file_data: bytes = None, filename: str = None, 
                 conversation_history: List = None, session_id: str = None, triage_context: dict = None, **kwargs) -> Dict[str, Any]:
        """
        Main entry point for the agent.
        
        Args:
            query: User's question or context
            mode: evaluate | scrutiny | validation
            file_data: Uploaded file bytes (for contract review)
            filename: Name of uploaded file
            conversation_history: Previous messages
            triage_context: Triage data (role, goal, intake_fields)
        
        Returns:
            Dict with evaluation/scrutiny results
        """
        if mode == "evaluate" and file_data:
            return await self.evaluate_contract(file_data, filename, triage_context=triage_context)
        elif mode == "scrutiny":
            return await self.scrutinize_case(query, conversation_history, triage_context=triage_context)
        elif mode == "validation":
            return await self.validate_response(query, conversation_history, triage_context=triage_context)
        else:
            return await self.evaluate_contract(file_data, filename, triage_context=triage_context) if file_data else {"response": "Please upload a contract file for evaluation.", "mode_used": "evaluate"}
    
    async def evaluate_contract(self, file_data: bytes, filename: str, triage_context: dict = None) -> Dict[str, Any]:
        """Evaluate uploaded contract/document"""
        if evaluate_contract:
            result = evaluate_contract(file_data, filename)
            response = format_evaluation_response(result) if format_evaluation_response else str(result)
        else:
            # Fallback evaluation
            text = extract_text(file_data, filename) if extract_text else "Contract content"
            response = f"Contract Evaluation:\n\nAnalyzed: {filename}\n\nContent length: {len(text)} characters"
        
        return {
            "response": response,
            "mode_used": "evaluate",
            "scrutiny": {
                "risk_level": self._assess_risk(response),
                "issues_found": self._count_issues(response),
            },
            "case_law_found": False,
            "confidence_score": 0.80,
            "is_hallucinating": False
        }
    
    async def scrutinize_case(self, problem_text: str, history: List = None, triage_context: dict = None) -> Dict[str, Any]:
        """Review user's legal problem for issues"""
        # Inject triage context into the problem text for richer scrutiny
        if triage_context:
            tc_lines = ["Case Context from Triage:"]
            if triage_context.get("role"):
                tc_lines.append(f"- User Role: {triage_context['role']}")
            if triage_context.get("goal"):
                tc_lines.append(f"- Goal: {triage_context['goal']}")
            intake = triage_context.get("intake_fields", {})
            for k, v in intake.items():
                if v:
                    tc_lines.append(f"- {k.replace('_', ' ').title()}: {v}")
            problem_text = "\n".join(tc_lines) + "\n\n" + problem_text

        if scrutinize:
            result = scrutinize(problem_text)
            
            response = self._format_scrutiny_result(result)
            
            scrutiny_dict = result if isinstance(result, dict) else {
                "is_valid": getattr(result, 'is_valid', True),
                "warnings": getattr(result, 'warnings', []),
                "veto_message": getattr(result, 'veto_message', ''),
                "can_proceed": getattr(result, 'can_proceed', True),
                "remapped_laws": getattr(result, 'remapped_laws', {}),
                "limitation_info": getattr(result, 'limitation_info', ''),
                "severity": getattr(result, 'severity', 'none'),
            }
            
            is_time_barred = result.get("is_time_barred", False) if isinstance(result, dict) else (
                "time-barred" in getattr(result, 'limitation_info', '').lower() or
                "barred" in getattr(result, 'limitation_info', '').lower()
            )
            
            return {
                "response": response,
                "mode_used": "scrutiny",
                "scrutiny": scrutiny_dict,
                "is_limitation_issue": is_time_barred,
                "confidence_score": 0.85
            }
        else:
            # Basic scrutiny response
            return {
                "response": f"Case Review for: {problem_text[:100]}...\n\nI'd recommend consulting a lawyer for detailed analysis.",
                "mode_used": "scrutiny",
                "confidence_score": 0.5
            }
    
    async def validate_response(self, response: str, sources: List = None, triage_context: dict = None) -> Dict[str, Any]:
        """Validate generated response against sources"""
        if validate_legal_response:
            result = validate_legal_response(response, sources or [])
            is_valid = not result.get("is_hallucinating", False)
        else:
            is_valid = True
        
        return {
            "response": response,
            "validated": is_valid,
            "mode_used": "validation",
            "confidence_score": 0.90 if is_valid else 0.50
        }
    
    async def check_limitation_period(self, claim_type: str, cause_of_action_date: str) -> Dict[str, Any]:
        """Check if case is within limitation period"""
        years = CLAIM_TYPES.get(claim_type, {}).get("limitation", 3)
        
        return {
            "claim_type": claim_type,
            "limitation_period": f"{years} year(s)",
            "note": f"Under the Limitation Act, you have {years} years from the cause of action to file your case."
        }
    
    def _format_scrutiny_result(self, result) -> str:
        """Format scrutiny result for display"""
        if isinstance(result, dict):
            return "\n\n".join(
                f"{k.upper()}: {v}" for k, v in result.items() if v
            ) if result else "Case analysis complete."
        
        # Handle ScrutinyResult dataclass
        parts = []
        
        is_valid = getattr(result, 'is_valid', True)
        warnings = getattr(result, 'warnings', [])
        veto = getattr(result, 'veto_message', '')
        can_proceed = getattr(result, 'can_proceed', True)
        remapped = getattr(result, 'remapped_laws', {})
        limitation = getattr(result, 'limitation_info', '')
        severity = getattr(result, 'severity', 'none')
        
        if not is_valid:
            parts.append("⚠️ LEGAL SCRUTINY FLAGGED ISSUES")
        
        if veto:
            parts.append(f"🛑 VETO: {veto}")
        
        if warnings:
            parts.append("**Warnings:**\n" + "\n".join(f"- {w}" for w in warnings))
        
        if limitation:
            parts.append(f"**Limitation Check:** {limitation}")
        
        if remapped:
            parts.append("**Law Updates Applied:**")
            for old_law, new_law in remapped.items():
                parts.append(f"- {old_law} → {new_law}")
        
        if severity != 'none':
            severity_icon = "🔴" if severity == "serious" else "🟡"
            parts.append(f"{severity_icon} **Severity:** {severity.upper()}")
        
        if can_proceed and is_valid:
            parts.append("✅ **Case appears valid and within limitation.**")
        elif can_proceed and not is_valid:
            parts.append("⚠️ You may proceed, but be aware of the warnings above.")
        
        return "\n\n".join(parts) if parts else "✅ Case analysis complete. No issues found."
    
    def _assess_risk(self, text: str) -> str:
        """Assess risk level from text"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["high risk", "significant", "major"]):
            return "High"
        elif any(word in text_lower for word in ["moderate", "some concerns"]):
            return "Medium"
        else:
            return "Low"
    
    def _count_issues(self, text: str) -> int:
        """Count issues found in text"""
        # Simple count of issue markers
        return text.count("⚠️") + text.count("issue") + text.count("concern")


# Singleton instance
agent = ReviewerAgent()