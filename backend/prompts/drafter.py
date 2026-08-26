"""
DRAFTER AGENT PROMPTS
=====================
Legal document drafting prompts
"""

# ============================================================
# SYSTEM PROMPT
# ============================================================

DRAFTER_SYSTEM_PROMPT = """You are a legal document drafting expert AI. Your role is to create properly formatted legal documents for Indian courts and legal proceedings.

Document Types You Can Draft:
1. Legal Notices (general, demand, warning)
2. Cheque Bounce Notices (Section 138 NIA)
3. Employment Notices (termination, demand, complaint)
4. FIR Complaints
5. Rental/Lease Agreements
6. Court Complaints/Applications

Guidelines:
- Use proper legal language and format
- Include all necessary parties with complete addresses
- Clearly state facts, grounds, and relief sought
- Include verification/signature blocks
- Reference relevant sections of applicable laws
- Be precise with dates, amounts, and details"""

# ============================================================
# LEGAL NOTICE PROMPT
# ============================================================

LEGAL_NOTICE_PROMPT = """Draft a Legal Notice with the following details:

FROM (Sender):
- Name: {sender_name}
- Address: {sender_address}

TO (Recipient):
- Name: {recipient_name}
- Address: {recipient_address}

SUBJECT: {subject}

DETAILS:
{details}

DEMAND/RELIEF:
{demand}

DEADLINE (if any): {deadline}

Include:
1. Proper legal notice heading
2. Address to the recipient
3. Subject line
4. Background/Facts
5. Legal grounds
6. Demand/Notice
7. Consequences of non-compliance
8. Verification by sender
9. Signature and date"""

# ============================================================
# CHEQUE BOUNCE NOTICE PROMPT
# ============================================================

CHEQUE_BOUNCE_NOTICE_PROMPT = """Draft a Legal Notice under Section 138 of Negotiable Instruments Act for CHEQUE BOUNCE:

CHEQUE DETAILS:
- Cheque Number: {cheque_number}
- Cheque Amount: Rs. {cheque_amount}
- Cheque Date: {cheque_date}
- Bank Name: {bank_name}
- Dishonour Date: {dishonour_date}
- Reason for Dishonour: {reason}

FROM:
- Name: {sender_name}
- Address: {sender_address}

TO:
- Name: {recipient_name}
- Address: {recipient_address}

DEMAND:
- Amount Demanded: Rs. {demand_amount}
- Deadline for Payment: {deadline} days from notice

Include:
1. Reference to Section 138 NIA
2. Details of the cheque and dishonour
3. Demand for payment within 15 days (mandatory under Section 138)
4. Warning of legal consequences
5. Verification and signature"""

# ============================================================
# EMPLOYMENT NOTICE PROMPT
# ============================================================

EMPLOYMENT_NOTICE_PROMPT = """Draft an Employment Legal Notice:

EMPLOYER:
- Name: {employer_name}
- Address: {employer_address}

EMPLOYEE:
- Name: {employee_name}
- Designation: {designation}
- Joining Date: {joining_date}

ISSUE:
{issue_description}

RELIEF SOUGHT:
{relief_sought}

DETAILS:
{details}

Include:
1. Employment details
2. Nature of issue (non-payment, termination, etc.)
3. Relevant labor law references
4. Demand/Notice
5. Deadline for response
6. Legal consequences"""

# ============================================================
# FIR COMPLAINT PROMPT
# ============================================================

FIR_COMPLAINT_PROMPT = """Draft an FIR (First Information Report) Complaint:

COMPLAINANT:
- Name: {complainant_name}
- Address: {complainant_address}

INCIDENT DETAILS:
- Date: {incident_date}
- Time: {incident_time}
- Place: {incident_place}

DESCRIPTION:
{description}

ACCUSED DETAILS (if known):
{accused_details}

WITNESSES (if any):
{witness_details}

RELIEF SOUGHT:
{relief_sought}

Include:
1. Proper format for police complaint
2. Details of incident
3. Sections applicable (BNS 2023)
4. Relief sought
5. Verification"""

# ============================================================
# RENTAL AGREEMENT PROMPT
# ============================================================

RENTAL_AGREEMENT_PROMPT = """Draft a Rental/Lease Agreement:

OWNER/LANDLORD:
- Name: {owner_name}
- Address: {owner_address}

TENANT:
- Name: {tenant_name}
- Address: {tenant_address}

PROPERTY:
- Address: {property_address}
- Description: {property_description}

TERMS:
- Monthly Rent: Rs. {rent_amount}
- Security Deposit: Rs. {security_deposit}
- Tenure: {tenure} months
- Notice Period: {notice_period} days

Include:
1. Property description
2. Terms and conditions
3. Rent payment terms
4. Maintenance responsibilities
5. Rights and obligations of both parties
6. Termination clause
7. Signature blocks for both parties"""

# ============================================================
# DOCUMENT FIELD VALIDATION
# ============================================================

FIELD_VALIDATION_PROMPT = """Validate the following fields for document:

Fields required: {required_fields}
Fields provided: {provided_fields}

Check for:
1. Missing required fields
2. Invalid formats (dates, amounts, addresses)
3. Consistency between fields
4. Completeness

Return any issues found."""

# ============================================================
# RESPONSE FORMATTING
# ============================================================

DRAFT_RESPONSE_FORMAT = """Format the document:
- Use proper heading (centered, bold)
- Use numbered paragraphs
- Use formal language
- Keep it clear and precise
- Include all necessary legal clauses
- End with proper closure"""