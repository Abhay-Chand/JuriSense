"""
SAULGPT — SCRUTINY AGENT
==========================
Pre-flight legal validation layer that runs BEFORE document
drafting begins. Acts as a senior advocate reviewing the matter
before putting pen to paper.

Three validation checks:

1. LIMITATION ACT 1963 — Checks if claim is time-barred
   Different limitation periods for different claim types:
   → Tort/injury:          3 years
   → Contract breach:      3 years
   → Money recovery:       3 years
   → Immovable property:  12 years
   → Cheque bounce:        1 month (notice period critical)
   → Service/employment:   3 years

2. REMEDY VALIDATOR — Checks if demand is legally recognized
   Flags non-legal "demands" like:
   → Blessings, forgiveness, servitude, apology as primary remedy
   Suggests proper legal equivalents

3. BNS/BNSS ENFORCER — Hard-codes 2024 law update
   Any mention of IPC/CrPC/Evidence Act for post-July 2024 incidents
   gets flagged and remapped to BNS/BNSS/BSA

Returns a ScrutinyResult with:
  is_valid        : bool — proceed or warn
  warnings        : list of specific warnings
  veto_message    : str  — shown to user if serious issue
  can_proceed     : bool — True even with warnings (user decides)
  remapped_laws   : dict — old law → new law substitutions

Used by:
  api_server.py → scrutinize_before_draft()
"""

import re
import os
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────

@dataclass
class ScrutinyResult:
    is_valid:       bool        = True
    warnings:       list        = field(default_factory=list)
    veto_message:   str         = ""
    can_proceed:    bool        = True   # user always decides
    remapped_laws:  dict        = field(default_factory=dict)
    limitation_info: str        = ""
    severity:       str         = "none"  # none / warning / serious


# ─────────────────────────────────────────────────────────────
# LIMITATION PERIODS (Limitation Act 1963)
# ─────────────────────────────────────────────────────────────

LIMITATION_PERIODS = {
    # Civil suits
    "money_recovery":       3,
    "contract_breach":      3,
    "tort_injury":          3,
    "defamation":           1,
    "cheque_bounce_notice": 0.083,  # 30 days from return date
    "cheque_bounce_suit":   1,      # 1 year from cause of action
    "employment":           3,
    "wages":                1,      # Payment of Wages Act
    "consumer":             2,      # Consumer Protection Act
    "immovable_property":   12,
    "mortgage":             12,
    "trust":                3,
    "default":              3,      # general default
}

# Keywords that hint at the type of claim
CLAIM_TYPE_HINTS = {
    "money_recovery":    ["money", "payment", "dues", "debt", "loan", "amount"],
    "contract_breach":   ["contract", "agreement", "breach", "deal", "terms"],
    "tort_injury":       ["assault", "attack", "injury", "hurt", "accident", "bite",
                          "defamation", "slap", "harassment"],
    "cheque_bounce":     ["cheque", "cheque bounce", "section 138", "dishonoured"],
    "employment":        ["salary", "wages", "fired", "terminated", "employment",
                          "job", "employer", "severance"],
    "consumer":          ["consumer", "product", "service deficiency", "refund"],
    "immovable_property": ["property", "land", "house", "flat", "possession"],
}


def detect_claim_type(problem_text: str) -> str:
    """Detects most likely claim type from problem description."""
    problem_lower = problem_text.lower()
    matches = {}
    for claim_type, hints in CLAIM_TYPE_HINTS.items():
        score = sum(1 for h in hints if h in problem_lower)
        if score > 0:
            matches[claim_type] = score
    if not matches:
        return "default"
    return max(matches, key=matches.get)


def get_limitation_years(claim_type: str) -> float:
    """Returns limitation period in years for a claim type."""
    return LIMITATION_PERIODS.get(claim_type, LIMITATION_PERIODS["default"])


# ─────────────────────────────────────────────────────────────
# DATE PARSER
# Handles multiple Indian date formats
# ─────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',          # DD/MM/YYYY or DD-MM-YYYY
    r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',          # YYYY-MM-DD
    r'\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|'
    r'May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
    r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b',  # DD Month YYYY
    r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|'
    r'May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
    r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b',  # Month YYYY
    r'\b(\d{4})\b',   # just a year
]

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3,   "apr": 4, "april": 4,
    "may": 5,               "jun": 6, "june": 6,
    "jul": 7, "july": 7,   "aug": 8, "august": 8,
    "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_date_from_text(text: str) -> Optional[date]:
    """
    Extracts and parses the most relevant date from text.
    Returns None if no parseable date found.
    """
    text = text.strip()

    # DD/MM/YYYY or DD-MM-YYYY
    m = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # YYYY-MM-DD
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # DD Month YYYY
    m = re.search(
        r'\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|'
        r'may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|'
        r'oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})\b',
        text, re.IGNORECASE
    )
    if m:
        try:
            month = MONTH_MAP[m.group(2).lower()[:3]]
            return date(int(m.group(3)), month, int(m.group(1)))
        except (ValueError, KeyError):
            pass

    # Month YYYY
    m = re.search(
        r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|'
        r'may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|'
        r'oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})\b',
        text, re.IGNORECASE
    )
    if m:
        try:
            month = MONTH_MAP[m.group(1).lower()[:3]]
            return date(int(m.group(2)), month, 1)
        except (ValueError, KeyError):
            pass

    # Just a 4-digit year
    m = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', text)
    if m:
        try:
            year = int(m.group(1))
            if year < 1900 or year > date.today().year + 1:
                return None
            return date(year, 1, 1)
        except ValueError:
            pass

    return None


# ─────────────────────────────────────────────────────────────
# LIMITATION ACT CHECK
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# LIMITATION EXCEPTIONS (Limitation Act 1963)
# ─────────────────────────────────────────────────────────────

ACKNOWLEDGMENT_PATTERNS = [
    r"\bpromis(?:ed|e)\s+to\s+pay\b", r"\backnowledg(?:ed|e)\b",
    r"\bsaid\s+(?:he|she|they)\s+will\s+pay\b", r"\brenewed\b",
    r"\bpart\s+payment\b", r"\bpaid\s+(?:some|part|rupees?)\b",
    r"\bconfirmed\s+the\s+(?:debt|amount|dues)\b",
    r"\bagreed\s+to\s+(?:pay|settle)\b",
    r"\b(?:gave|issued)\s+(?:a\s+)?post[-\s]?dated\s+cheque\b",
    r"\bwill\s+(?:clear|settle|pay)\s+(?:it|the\s+amount|next\s+month)\b",
]

CONTINUOUS_WRONG_PATTERNS = [
    r"\b(?:still|ongoing|continuing|continuous)\b",
    r"\bevery\s+(?:day|month|week|year)\b",
    r"\bstill\s+(?:not\s+)?(?:paying|occupying|using|causing)\b",
    r"\bcontinues?\s+to\b",
]

DISABILITY_PATTERNS = [
    r"\bminor\b", r"\bchild\b", r"\bmental\s+(?:illness|health|disability)\b",
    r"\bintellectual\s+disability\b", r"\b(?:was|is|were)\s+(?:a\s+)?minor\b",
    r"\bunder\s+18\b", r"\bbelow\s+18\b",
]

GOVERNMENT_PATTERNS = [
    r"\bgovernment\b", r"\bpublic\s+officer\b", r"\bstate\s+government\b",
    r"\bcentral\s+government\b", r"\bmunicipal\b", r"\bcps?u\b",
    r"\bpublic\s+sector\b",
]


def detect_limitation_exceptions(problem_description: str) -> dict:
    """
    Detect facts in the problem description that trigger
    limitation exceptions under the Limitation Act 1963.
    """
    desc_lower = problem_description.lower()
    exceptions = {}

    # Section 18 — Acknowledgment
    for pat in ACKNOWLEDGMENT_PATTERNS:
        if re.search(pat, desc_lower):
            exceptions["acknowledgment"] = (
                "The debtor appears to have acknowledged the liability "
                "(e.g., promised to pay, made part payment). Under Section 18 of the "
                "Limitation Act, 1963, a fresh limitation period starts from the "
                "date of such acknowledgment. This claim may NOT be time-barred."
            )
            break

    # Sections 22-23 — Continuous wrong
    for pat in CONTINUOUS_WRONG_PATTERNS:
        if re.search(pat, desc_lower):
            exceptions["continuous_wrong"] = (
                "This appears to be a continuing wrong. Under the Limitation Act, "
                "a fresh period of limitation begins at every moment the wrong continues. "
                "Time is counted from when the continuing wrong ceases, not from its start."
            )
            break

    # Sections 6-8 — Disability (minor, mental health)
    for pat in DISABILITY_PATTERNS:
        if re.search(pat, desc_lower):
            exceptions["disability"] = (
                "The plaintiff appears to have been under a disability (minority, "
                "mental illness, or intellectual disability) when the cause of action "
                "arose. Under Sections 6-8 of the Limitation Act, 1963, the limitation "
                "period is extended until 3 years after the disability ceases."
            )
            break

    # Section 80 CPC — Government notice
    for pat in GOVERNMENT_PATTERNS:
        if re.search(pat, desc_lower):
            exceptions["government_notice"] = (
                "The opposing party appears to be a government entity. Under "
                "Section 80 of the Code of Civil Procedure, 1908, a 60-day notice "
                "must be given to the government before filing a civil suit. "
                "This notice period does not extend the limitation period, so "
                "file the notice early."
            )
            break

    return exceptions


def format_exception_notes(exceptions: dict) -> str:
    """Format detected exceptions into human-readable notes."""
    if not exceptions:
        return ""
    parts = ["\n\n**Possible Limitation Exceptions:**"]
    for key, note in exceptions.items():
        parts.append(f"\n• {note}")
    return "".join(parts)


def check_limitation(
    incident_date_text: str,
    problem_description: str
) -> tuple[bool, str, str]:
    """
    Checks if a claim is time-barred under the Limitation Act 1963.
    Now detects and reports limitation exceptions.

    Args:
        incident_date_text:   text containing the date of incident
        problem_description:  full problem description for claim type detection

    Returns:
        (is_time_barred, warning_message, info_message)
    """
    incident_date = parse_date_from_text(incident_date_text)

    if incident_date is None:
        return False, "", "Could not parse incident date for limitation check."

    today      = date.today()
    years_ago  = (today - incident_date).days / 365.25

    # Detect claim type
    claim_type  = detect_claim_type(problem_description)
    limit_years = get_limitation_years(claim_type)

    # Detect limitation exceptions
    exceptions = detect_limitation_exceptions(problem_description)
    exception_notes = format_exception_notes(exceptions)

    # Check if ancient — before 1900 is clearly invalid
    if incident_date.year < 1900:
        return True, (
            f"⚠️ LIMITATION ISSUE: The incident date ({incident_date}) is "
            f"from the year {incident_date.year}. Legal notices can only be sent "
            f"for recent events. Claims this old cannot be filed under Indian law."
        ), ""

    # Check limitation period
    if years_ago > limit_years:
        years_int = int(years_ago)
        # If an exception is detected, downgrade to warning (not time-barred)
        if exceptions:
            return False, (
                f"⚠️ LIMITATION NOTE: This incident occurred approximately "
                f"{years_int} year(s) ago, which exceeds the standard {int(limit_years)}-year "
                f"limitation period for {claim_type.replace('_', ' ')} claims. "
                f"However, the following exception(s) may apply:"
                + exception_notes +
                "\n\nA lawyer should confirm whether the exception applies to your specific facts."
            ), f"Standard limit: {limit_years} years | Elapsed: {years_int} years | Exception(s) detected: {', '.join(exceptions.keys())}"
        else:
            return True, (
                f"⚠️ LIMITATION WARNING: This incident occurred approximately "
                f"{years_int} year(s) ago. Under the Limitation Act, 1963, "
                f"claims of this type ({claim_type.replace('_', ' ')}) must typically "
                f"be filed within **{int(limit_years)} year(s)**. "
                f"This claim may be **time-barred**. The notice can still be sent, "
                f"but a court may not admit a suit based on it."
            ), f"Limitation period: {limit_years} years | Time elapsed: {years_int} years"

    # Warn if approaching limitation
    remaining = limit_years - years_ago
    if remaining < 0.5:
        months = int(remaining * 12)
        return False, (
            f"⏰ LIMITATION ALERT: Only approximately **{months} month(s)** "
            f"remain before this claim becomes time-barred. "
            f"Act quickly."
            + exception_notes
        ), ""

    return False, "", f"Within limitation period ({int(years_ago * 12)} months elapsed of {int(limit_years * 12)} months allowed){exception_notes}"


# ─────────────────────────────────────────────────────────────
# REMEDY VALIDATOR
# ─────────────────────────────────────────────────────────────

NON_LEGAL_REMEDIES = [
    "blessing", "blessings", "forgiveness", "sorry", "apology",
    "servitude", "slavery", "worship", "prayer", "divine",
    "curse removed", "good luck", "karma",
]

LEGAL_REMEDY_SUGGESTIONS = {
    "blessing":    "Liquidated Damages",
    "forgiveness": "Public Apology + Damages",
    "apology":     "Damages + Written Apology",
    "servitude":   "Specific Performance or Compensation",
    "default":     "Monetary Compensation",
}


def check_remedy(demand_text: str) -> tuple[bool, str]:
    """
    Checks if the demanded remedy is legally recognized.

    Args:
        demand_text: what the user is demanding

    Returns:
        (is_invalid, warning_message)
    """
    demand_lower = demand_text.lower()

    for non_legal in NON_LEGAL_REMEDIES:
        if non_legal in demand_lower:
            suggestion = LEGAL_REMEDY_SUGGESTIONS.get(
                non_legal,
                LEGAL_REMEDY_SUGGESTIONS["default"]
            )
            return True, (
                f"⚠️ REMEDY WARNING: **'{demand_text}'** is not a recognized "
                f"legal remedy under Indian law. Legal notices can only demand "
                f"enforceable remedies. Consider demanding: "
                f"**{suggestion}** instead."
            )

    return False, ""


# ─────────────────────────────────────────────────────────────
# BNS/BNSS ENFORCER
# ─────────────────────────────────────────────────────────────

# July 1, 2024 — three major laws replaced
BNS_CUTOFF = date(2024, 7, 1)

LAW_REMAPPING = {
    "IPC":                    "BNS (Bharatiya Nyaya Sanhita, 2023)",
    "Indian Penal Code":      "BNS (Bharatiya Nyaya Sanhita, 2023)",
    "CrPC":                   "BNSS (Bharatiya Nagarik Suraksha Sanhita, 2023)",
    "Code of Criminal Procedure": "BNSS (Bharatiya Nagarik Suraksha Sanhita, 2023)",
    "Indian Evidence Act":    "BSA (Bharatiya Sakshya Adhiniyam, 2023)",
    "IEA":                    "BSA (Bharatiya Sakshya Adhiniyam, 2023)",
}


def check_law_currency(
    problem_text: str,
    incident_date_text: str = ""
) -> tuple[dict, str]:
    """
    Checks if outdated laws are cited for post-July 2024 incidents.

    Args:
        problem_text:       full problem description
        incident_date_text: date string from interview

    Returns:
        (remapped_laws, warning_message)
    """
    # Parse incident date
    incident_date = parse_date_from_text(incident_date_text) if incident_date_text else None

    # If incident is post-BNS cutoff, enforce remapping
    is_post_bns = (
        incident_date is None   # unknown date — warn anyway
        or incident_date >= BNS_CUTOFF
    )

    remapped = {}
    found_old_laws = []

    for old_law, new_law in LAW_REMAPPING.items():
        if old_law.lower() in problem_text.lower():
            remapped[old_law] = new_law
            found_old_laws.append(old_law)

    if found_old_laws and is_post_bns:
        law_list = ", ".join(found_old_laws)
        warning  = (
            f"⚖️ LAW UPDATE: You mentioned **{law_list}**, which was "
            f"replaced effective July 1, 2024. For incidents after this date, "
            f"the document will automatically use the updated legislation:\n"
            + "\n".join(f"  • {o} → {r}" for o, r in remapped.items())
        )
        return remapped, warning

    return {}, ""


# ─────────────────────────────────────────────────────────────
# MASTER SCRUTINY FUNCTION
# ─────────────────────────────────────────────────────────────

def scrutinize(
    problem_description: str,
    collected_fields:     dict = None,
) -> ScrutinyResult:
    """
    Master pre-flight scrutiny function.
    Runs all three checks and returns a consolidated result.

    Args:
        problem_description: original user problem statement
        collected_fields:    dict of {key: value} from interview
                             may contain: incident_date, relief_sought,
                             demand, amount etc.

    Returns:
        ScrutinyResult with all findings
    """
    result   = ScrutinyResult()
    fields   = collected_fields or {}

    # 1. Extract Date
    incident_date_text = (
        fields.get("incident_date", "") or 
        fields.get("date_of_incident", "") or 
        fields.get("incident_details", "") or # Sometimes users put dates in details
        ""
    )

    # 2. Extract Demand
    demand_text = (
        fields.get("relief_sought", "") or 
        fields.get("demand", "") or 
        fields.get("reason", "") or 
        ""
    )

    # ── Check 1: Limitation Act ──
    if incident_date_text or problem_description:
        date_to_check = incident_date_text if incident_date_text else problem_description
        is_barred, limitation_warning, limitation_info = check_limitation(
            date_to_check, 
            problem_description
        )
        if limitation_warning:
            result.warnings.append(limitation_warning)
            result.limitation_info = limitation_info
            if is_barred:
                result.severity    = "serious"
                result.is_valid    = False
                result.can_proceed = False
            else:
                # Not time-barred (possibly due to exceptions), keep can_proceed
                result.severity    = "warning" if result.severity == "none" else result.severity
        elif limitation_info and "Exception" in limitation_info:
            # Within limitation but exceptions exist — note them
            result.limitation_info = limitation_info
            if result.severity == "none":
                result.severity = "info"

    # ── Check 2: Remedy Validator ──
    if demand_text:
        is_invalid, remedy_warning = check_remedy(demand_text)
        if is_invalid:
            result.warnings.append(remedy_warning)
            if result.severity != "serious":
                result.severity = "warning"

    # ── Check 3: BNS/BNSS Enforcer ──
    remapped, law_warning = check_law_currency(
        problem_description,
        incident_date_text
    )
    if law_warning:
        result.warnings.append(law_warning)
        result.remapped_laws = remapped
        if result.severity == "none":
            result.severity = "info"

    # 3. Build the Veto Message
    if result.warnings:
        header = {
            "serious": "🚨 LEGAL SCRUTINY — ACTION REQUIRED",
            "warning": "⚠️ LEGAL SCRUTINY — WARNINGS",
            "info":    "ℹ️ LEGAL SCRUTINY — NOTES",
        }.get(result.severity, "ℹ️ LEGAL SCRUTINY")

        result.veto_message = (
            f"**{header}**\n\n" + 
            "\n\n".join(result.warnings)
        )

    return result


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("-" * 60)
    print("SaulGPT — Scrutiny Agent Test")
    print("-" * 60)

    tests = [
        {
            "problem": "My neighbor assaulted me",
            "fields":  {"incident_date": "15 January 1000", "demand": "blessings"},
            "label":   "Ancient date + invalid remedy"
        },
        {
            "problem": "My employer under IPC section 405 cheated me",
            "fields":  {"incident_date": "10 March 2025"},
            "label":   "Post-BNS IPC reference"
        },
        {
            "problem": "My tenant hasn't paid rent for 6 months",
            "fields":  {"incident_date": "January 2020"},
            "label":   "Time-barred claim"
        },
        {
            "problem": "My cheque of 3 lakhs bounced yesterday",
            "fields":  {"incident_date": "20 March 2026"},
            "label":   "Recent valid claim"
        },
    ]

    for t in tests:
        print(f"\n{'='*55}")
        print(f"Test: {t['label']}")
        print(f"Problem: {t['problem']}")
        result = scrutinize(t["problem"], t["fields"])
        print(f"Severity: {result.severity}")
        print(f"Can proceed: {result.can_proceed}")
        if result.veto_message:
            print(f"Message:\n{result.veto_message}")
        else:
            print("✅ No issues found")

    print("\n" + "=" * 60)
    print("Scrutiny Agent test complete.")
