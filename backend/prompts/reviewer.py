"""
REVIEWER AGENT PROMPTS
======================
Contract review, scrutiny, validation prompts
"""

# ============================================================
# SYSTEM PROMPT
# ============================================================

REVIEWER_SYSTEM_PROMPT = """You are a legal scrutiny and contract review expert AI. Your role is to:

1. Evaluate contracts and legal documents for risks
2. Check if cases are within limitation periods
3. Identify missing clauses and weaknesses
4. Suggest improvements and protections
5. Verify legal validity

You are cautious and thorough - better to flag potential issues than miss them.

Guidelines:
- Be critical but constructive
- Identify specific risks, not just general warnings
- Suggest concrete improvements
- Consider both parties' interests
- Flag any unusual or one-sided clauses"""

# ============================================================
# CONTRACT EVALUATION PROMPT
# ============================================================

CONTRACT_EVALUATION_PROMPT = """Evaluate this contract/document:

DOCUMENT:
{document_text}

FILENAME: {filename}

Provide a structured evaluation:

### RISK LEVEL
- High Risk
- Medium Risk  
- Low Risk

### ISSUES FOUND
List each issue with:
- Location in document
- Description of issue
- Risk level (High/Medium/Low)
- Suggested fix

### POSITIVE CLAUSES
Good provisions that protect interests

### MISSING CLAUSES
Essential clauses that should be added

### RECOMMENDATIONS
Overall advice on whether to sign/proceed

### SUMMARY
Brief overall assessment"""

# ============================================================
# LEGAL SCRUTINY PROMPT
# ============================================================

LEGAL_SCRUTINY_PROMPT = """Conduct legal scrutiny of this case:

CASE DESCRIPTION:
{case_description}

PARTY DETAILS:
{party_details}

Provide scrutiny on:

### LIMITATION CHECK
- What is the limitation period for this type of case?
- When did the cause of action arise?
- Is the case still within limitation?
- What happens if time-barred?

### REMEDIES
- What legal remedies are available?
- Which is the best course of action?
- What are the chances of success?

### RISK ASSESSMENT
- What are the risks of pursuing this case?
- What could go wrong?
- How can risks be mitigated?

### PROCEDURE
- What is the recommended procedure?
- What documents are needed?
- What is the timeline?

### CONCLUSION
- Should the client proceed?
- What additional information is needed?"""

# ============================================================
# LIMITATION PERIOD CHECK
# ============================================================

LIMITATION_CHECK_PROMPT = """Check limitation period for:

CLAIM TYPE: {claim_type}
CAUSE OF ACTION DATE: {cause_of_action_date}
CURRENT DATE: {current_date}

Provide:
1. Applicable limitation period under Limitation Act 1963
2. Whether case is within limitation
3. Days/months remaining (if applicable)
4. Options if case is time-barred
5. Any exceptions to limitation

Common limitation periods:
- Money recovery: 3 years
- Cheque bounce: 3 years
- Defamation: 1 year
- Motor accident: 2 years
- Consumer complaints: 2 years
- Property disputes: 3 years"""

# ============================================================
# DOCUMENT VALIDATION PROMPT
# ============================================================

DOCUMENT_VALIDATION_PROMPT = """Validate this legal response:

RESPONSE GENERATED:
{response}

SOURCES/CITATIONS:
{sources}

Check:
1. Are citations accurate and valid?
2. Do cited sections exist in the mentioned acts?
3. Are any cited laws repealed?
4. Does the response match the query?
5. Any hallucinations or fabrications?

Return:
- is_valid: true/false
- issues: list of any problems found
- confidence_score: 0-1"""

# ============================================================
# CLAUSE ANALYSIS PROMPT
# ============================================================

CLAUSE_ANALYSIS_PROMPT = """Analyze this clause in the contract:

CLAUSE TEXT:
{clause}

CONTEXT:
{context}

Analyze:
1. What does this clause mean in plain language?
2. Who does it benefit more?
3. What are the implications?
4. Is it standard or unusual?
5. Should it be negotiated?

Provide clear, practical advice."""

# ============================================================
# RED FLAG PROMPT
# ============================================================

RED_FLAGS_PROMPT = """Identify red flags in this document:

DOCUMENT:
{document}

Look for:
1. One-sided clauses favoring one party
2. Unusual or excessive penalties
3. Hidden fees or costs
4. Automatic renewal terms
5. Waiver of rights
6. Unclear language
7. Missing essential terms
8. Unconscionable provisions

List each red flag with severity."""

# ============================================================
# RESPONSE FORMATTING
# ============================================================

REVIEW_RESPONSE_FORMAT = """Format your review:
- Use ### for sections
- Use bullet points for lists
- Bold for key terms
- Clear headings for each analysis section
- Summary at the end"""

# ============================================================
# VETO CHECK PROMPT
# ============================================================

VETO_CHECK_PROMPT = """Check if this legal matter should proceed:

CASE SUMMARY: {case_summary}

Consider:
1. Is the case time-barred?
2. Is there a valid cause of action?
3. Are there jurisdictional issues?
4. What is the probability of success?
5. Are there counter-claims risks?

Return:
- can_proceed: true/false
- veto_reason: if cannot proceed, why
- warnings: list of concerns
- severity: minor/moderate/serious/blocking"""