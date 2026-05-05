from core.llm_client import LLMClient
from core.classifier import get_party_labels, ContractType

llm = LLMClient()


# Type‑specific report requirements to prevent cross‑contamination
TYPE_SPECIFIC_INSTRUCTIONS = {
    "consumer_loan": """
This is a CONSUMER LOAN AGREEMENT between a LENDER and a BORROWER.
Apply lending law ONLY. Do NOT apply employment, labor, or HR frameworks.

Mandatory checks — you MUST address each of these in the report:
1. Interest rate vs. state usury caps (NY: 16% civil usury limit, 25% criminal usury)
2. Collateral/financed asset description completeness (UCC Article 9)
3. PII exposure — is SSN, DOB, or other sensitive data in plain text?
4. Repossession/default — does the clause require written notice before enforcement? (UCC 9-611)
5. Prepayment penalties, late fees, acceleration clauses — are they disclosed and reasonable?
6. Truth in Lending Act (TILA) disclosures — APR, finance charge, payment schedule

Party context: "Termination" means contract termination/default, NOT employment firing.
The relationship is borrower-lender, not employer-employee.

Recommended Actions must be lending‑specific, such as:
- "Replace the variable interest rate (CPI-adjusted) with a fixed APR below 16% to comply with NY civil usury cap"
- "Define the financed asset with a specific description (make, model, VIN/serial) in the preamble"
- "Redact Borrower's SSN and all PII from the document; store separately in encrypted format"
- "Add a mandatory 30‑day written notice of default and opportunity to cure before repossession"
- "Add a clear prepayment clause stating whether penalties apply and at what rate"
- "Include a TILA disclosure box with APR, finance charge, total of payments, and payment schedule"
""",

    "employment": """
This is an EMPLOYMENT AGREEMENT between an EMPLOYER and an EMPLOYEE.
Apply employment/labor law ONLY.

Mandatory checks:
1. Working hours, overtime, and rest break compliance (FLSA)
2. Leave entitlements (sick, annual, parental)
3. Termination notice period and severance
4. Employee liability scope — is it capped and proportionate?
5. Non‑compete and confidentiality scope — are they reasonable in duration and geography?
6. Dispute resolution — is it neutral or one‑sided?

Party context: "Termination" means end of employment relationship.

Recommended Actions must be employment‑specific, such as:
- "Add a mandatory employer termination notice period of at least 30 days"
- "Add an overtime compensation clause for work beyond 40 hours/week"
- "Replace unlimited employee liability with a capped, proportionate clause"
""",

    "nda": """
This is a NON‑DISCLOSURE AGREEMENT between a DISCLOSING PARTY and a RECEIVING PARTY.
Apply confidentiality/trade secret law ONLY.

Mandatory checks:
1. Definition of "Confidential Information" — is it specific or overbroad?
2. Duration of obligation — is it perpetual or time‑limited?
3. Exclusions from confidentiality — are they clearly stated?
4. Return/destruction obligations upon termination
5. Remedies for breach — injunctive relief, liquidated damages

Recommended Actions must be NDA‑specific.
""",

    "student_loan": """
This is a STUDENT LOAN AGREEMENT.
Apply educational lending law ONLY.

Mandatory checks:
1. TILA and Higher Education Act disclosures
2. APR, finance charge, and payment schedule accuracy
3. Deferment and forbearance options
4. Prepayment and consolidation rights
5. Co‑signer release conditions (if applicable)

Recommended Actions must be student‑loan‑specific.
""",

    "lease": """
This is a LEASE AGREEMENT between a LANDLORD/LESSOR and a TENANT/LESSEE.
Apply property/landlord‑tenant law ONLY.

Mandatory checks:
1. Security deposit amount and return timeline per state law
2. Maintenance and repair obligations
3. Eviction notice and cure period
4. Rent increase and renewal terms
5. Subletting and assignment restrictions

Recommended Actions must be lease‑specific.
""",

    "service_agreement": """
This is a SERVICE/VENDOR AGREEMENT between a CLIENT and a VENDOR/SERVICE PROVIDER.
Apply commercial contract law ONLY.

Mandatory checks:
1. Scope of work and deliverables — are they defined and measurable?
2. Payment terms — are milestones, invoice schedule, and late fees specified?
3. Limitation of liability — is it mutual and reasonable?
4. Termination — are notice periods, cure periods, and post-termination obligations clear?
5. Independent contractor classification — is the vendor clearly NOT an employee?
6. IP ownership — who owns work product and deliverables?
7. Insurance requirements — are minimum coverage amounts specified?
8. Governing law and dispute resolution — are jurisdiction and method specified?

Recommended Actions must be service‑agreement‑specific, such as:
- "Define deliverables with specific quantities, deadlines, and acceptance criteria"
- "Add a clear payment schedule with milestone-based payments and late fee provisions"
- "Specify minimum insurance coverage amounts (general liability, professional liability, workers' comp)"
- "Add a clear IP ownership clause specifying that work product belongs to Client upon full payment"
""",

    "other": """
This is a GENERAL CONTRACT.
Apply universal contract law principles.

Mandatory checks:
1. Are material terms defined and unambiguous?
2. Are consideration, offer, and acceptance elements present?
3. Are termination and breach provisions clear?
4. Is dispute resolution neutral?
5. Are there contradictory clauses or internal inconsistencies?
6. Are signatures, dates, and party identification present?

Recommended Actions must be contract‑general.
""",
}


def _build_executor_prompt(
    plan: list,
    context: list,
    doc_type: str,
    document_text: str,
    parties: dict,
    pre_detected_issues: list,
) -> str:
    """
    Build a type‑specific executor prompt that prevents cross‑domain
    contamination and enforces severity consistency.
    """
    
    plan_str = "\n".join(f"- {item}" for item in plan) if plan else "No plan provided."
    context_str = "\n\n".join(context[:10]) if context else "No additional legal context retrieved."
    document_excerpt = document_text[:5000]
    
    # Include pre-detected issues
    issues_str = ""
    if pre_detected_issues:
        issues_str = "\nPRE-DETECTED STRUCTURAL ISSUES (must be addressed in report):\n"
        for issue in pre_detected_issues:
            issues_str += f"- [{issue['severity']}] {issue['detail']}\n"
    
    type_instructions = TYPE_SPECIFIC_INSTRUCTIONS.get(
        doc_type,
        TYPE_SPECIFIC_INSTRUCTIONS["other"]
    )
    
    return f"""You are a senior compliance analyst preparing a production‑quality compliance risk assessment.

DOCUMENT TYPE: {doc_type}
PARTY RELATIONSHIP: {parties.get('party_a', 'Party A')} and {parties.get('party_b', 'Party B')} in a {parties.get('relationship', 'contractual')} relationship.

{type_instructions}

AUDIT PLAN:
{plan_str}
{issues_str}
SOURCE DOCUMENT EXCERPT:
{document_excerpt}

RETRIEVED LEGAL CONTEXT:
{context_str}

---

Write a structured professional report with these exact sections:

## Executive Summary
- State the document type, parties, and overall risk level
- Summarize the 2‑3 most critical findings

## Structural Issues
- List any blank fields, missing signatures, missing dates, or other structural problems
- Reference the actual document sections where these occur

## High Risk Clauses
- Reference clauses by their ACTUAL labels from the document (e.g., "TERMINATION section" not "Clause 5.1")
- If the document uses named sections, use those names. If it uses numbers, use those numbers.
- Explain why each clause creates legal/compliance risk
- Cite relevant legal standards from the retrieved context

## Compliance Violations
- List specific statutory/regulatory violations identified
- Include the legal basis for each violation

## Business Impact
- Describe operational, financial, and reputational exposure
- Quantify where possible (penalty ranges, litigation risk)

## Risk Severity Table
| Clause/Section | Risk | Severity | Legal Basis |
|--------|------|----------|-------------|
| Section Name | Description | LOW/MEDIUM/HIGH/CRITICAL | Statute/Regulation |

## Recommended Actions
1. **Action** — tie to specific clause and risk above
2. **Action** — be concrete: what language to add, replace, cap, clarify, or remove

## Confidence Score
- Score 0‑100 reflecting evidentiary support and legal precision
- Note any limitations (missing clauses, unclear jurisdiction)

---

CRITICAL RULES — VIOLATION = INCORRECT REPORT:

1. SEVERITY CONSISTENCY: Each clause must receive EXACTLY ONE severity rating. If you mention the same clause in multiple sections, use the SAME severity.

2. PARTY ROLES: Interpret ALL terms based on the {parties.get('relationship', 'contractual')} relationship. "Termination" means end of THIS contract type, not firing.

3. DOMAIN BOUNDARIES: If this is a {doc_type}, do NOT apply employment, labor, or HR frameworks. Do NOT check working hours, leave, overtime, employee liability, or employer notice unless doc_type is "employment".

4. MANDATORY CHECKS: You MUST address every mandatory check listed in the type‑specific instructions above. If a check finds no issue, report it as compliant.

5. RECOMMENDATIONS: Every recommendation must be specific to {doc_type}. Use the language patterns provided in the type‑specific instructions.

6. NO VAGUE LANGUAGE: Never write "review and update" or "improve process." Always specify exact contractual language changes.

7. CLAUSE REFERENCING: Reference clauses by their ACTUAL labels from the document (e.g., "SCOPE OF ENGAGEMENT section" or "TERMINATION section"). Do NOT invent clause numbers like "Clause 5.1" if the document uses named sections. Quote the actual section heading.

8. ADDRESS PRE-DETECTED ISSUES: If pre-detected structural issues are listed above, you MUST include them in the Structural Issues section of the report.

Draft Report:"""


def executor_node(state: dict) -> dict:
    # GATE: Handle non-auditable documents
    if state.get("document_type") == "non_auditable":
        return {
            "draft_report": "## ⚠️ Cannot Audit This Document\n\n" + 
                           state.get("error", "Invalid document type. Please upload a contract, policy, or legal agreement.")
        }
    
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    doc_type = state.get("document_type", "other")
    document_text = state.get("document_text", "")
    pre_detected_issues = state.get("pre_detected_issues", [])
    
    # Get party labels for this document type
    try:
        contract_type = ContractType(doc_type)
    except ValueError:
        contract_type = ContractType.OTHER
    parties = get_party_labels(contract_type)
    
    prompt = _build_executor_prompt(
        plan=plan,
        context=context,
        doc_type=doc_type,
        document_text=document_text,
        parties=parties,
        pre_detected_issues=pre_detected_issues,
    )
    
    draft = llm.generate(prompt, max_tokens=2000)
    return {"draft_report": draft}