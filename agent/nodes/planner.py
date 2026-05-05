"""
Planner node: Classifies the document, validates it's auditable,
detects structural issues, and generates a type‑specific compliance audit plan.
"""
import json
import re
from core.llm_client import LLMClient
from core.classifier import classify_document, get_party_labels, detect_document_issues, ContractType

llm = LLMClient()


def _is_auditable_document(text: str, doc_type: ContractType) -> bool:
    """
    Check if the document is actually a contract, policy, or legal agreement.
    Prevents hallucination on CSVs, spreadsheets, or non-legal text.
    """
    # If classifier found a specific contract type, trust it
    if doc_type != ContractType.OTHER:
        return True
    
    # For "other" — check for contract-like structure
    contract_indicators = [
        r"(agreement|contract|terms\s+and\s+conditions|parties|clause|section|article)",
        r"(shall|must|will|agrees?\s+to|obligations?\s+of)",
        r"(termination|breach|indemnify|warranty|representation)",
        r"(governing\s+law|jurisdiction|arbitration|dispute\s+resolution)",
        r"(hereinafter|hereto|whereas|hereby|aforesaid)",
    ]
    
    text_lower = text.lower()
    matches = sum(1 for pattern in contract_indicators if re.search(pattern, text_lower))
    
    return matches >= 2  # At least 2 contract-like patterns required


def build_plan_prompt(document_text: str, doc_type: ContractType, parties: dict, issues: list) -> str:
    """
    Build a prompt that forces the LLM to generate a plan specific to the
    contract type, never falling back to generic/employment language.
    """
    
    # Include pre-detected issues in the prompt
    issues_str = ""
    if issues:
        issues_str = "\nPre-detected structural issues (MUST be included in plan):\n"
        for issue in issues:
            issues_str += f"- [{issue['severity']}] {issue['detail']}\n"
    
    type_instructions = {
        ContractType.CONSUMER_LOAN: """This is a consumer loan agreement between a {party_b} and a {party_a}.
Generate a compliance audit plan focused ONLY on lending law:
- Verify interest rate against state and federal usury caps (NY: 16% civil, 25% criminal)
- Check if collateral/financed asset is clearly described (UCC 2-201)
- Inspect for exposed PII (SSN, DOB) in plain text
- Validate repossession and default provisions comply with UCC 9-611 notice requirements
- Assess prepayment penalties, late fees, and acceleration clauses
- Verify Truth in Lending Act disclosures (APR, finance charge, payment schedule)""",
        
        ContractType.EMPLOYMENT: """This is an employment agreement between an {party_a} and an {party_b}.
Generate a compliance audit plan focused ONLY on employment law:
- Check working hours, overtime, and rest break compliance (FLSA)
- Verify leave entitlements (sick, annual, parental)
- Assess termination notice periods and severance
- Review employee liability and indemnification
- Check non‑compete and confidentiality scope
- Verify dispute resolution and governing law""",
        
        ContractType.NDA: """This is a non‑disclosure agreement between a {party_a} and {party_b}.
Generate a compliance audit plan focused ONLY on confidentiality:
- Verify definition of confidential information is clear
- Check duration of confidentiality obligations
- Assess exclusions from confidentiality
- Review return/destruction of confidential materials
- Check for non‑circumvention or non‑compete overreach""",
        
        ContractType.STUDENT_LOAN: """This is a student loan agreement between a {party_b} and a {party_a}.
Generate a compliance audit plan focused ONLY on educational lending:
- Verify Truth in Lending Act and Higher Education Act compliance
- Check for required disclosures (APR, deferment, forbearance)
- Assess prepayment and consolidation options
- Verify in‑school deferment provisions""",
        
        ContractType.LEASE: """This is a lease agreement between a {party_a} and a {party_b}.
Generate a compliance audit plan focused ONLY on property leasing:
- Check security deposit handling and return timeline
- Verify maintenance and repair obligations
- Assess eviction and default procedures
- Review rent increase and renewal terms""",
        
        ContractType.SERVICE_AGREEMENT: """This is a service/vendor agreement between a {party_a} and a {party_b}.
Generate a compliance audit plan focused ONLY on service delivery:
- Verify scope of work and deliverables are defined
- Check payment terms and milestone triggers
- Assess limitation of liability and indemnification
- Review termination for convenience and cause
- Verify independent contractor classification (if applicable)
- Check IP ownership and licensing terms
- Verify insurance requirements are specified""",
        
        ContractType.OTHER: """This is a general contract.
Generate a compliance audit plan focusing on universal contract risks:
- Check for ambiguous or undefined terms
- Verify consideration, offer, and acceptance elements
- Assess termination and breach provisions
- Review dispute resolution and governing law
- Flag missing signatures, dates, or parties""",
    }
    
    instruction = type_instructions.get(
        doc_type,
        type_instructions[ContractType.OTHER]
    ).format(**parties)
    
    return f"""{instruction}
{issues_str}
Document excerpt:
{document_text[:2000]}

Return ONLY valid JSON:
{{"plan": ["task 1", "task 2", "task 3", "task 4", "task 5", "task 6"]}}

CRITICAL RULES:
- Every task must be about compliance, legal risk, or enforceability for THIS specific contract type
- Do NOT include tasks about employment, labor law, or employee rights unless this IS an employment contract
- Do NOT include generic tasks like "Summarize document" or "Identify key points"
- Each task should mention a specific clause type or legal standard to verify
- If pre-detected structural issues are listed above, include them in the plan"""


def planner_node(state: dict) -> dict:
    """
    Orchestrator function called by LangGraph.
    Classifies the document, validates it, generates type‑specific plan.
    """
    document_text = state.get("document_text", "")
    
    # Step 1: Classify using deterministic rules
    doc_type = classify_document(document_text)
    
    # Step 2: VALIDATION GATE — reject non-auditable documents
    if not _is_auditable_document(document_text, doc_type):
        return {
            "plan": [],
            "document_type": "non_auditable",
            "error": "⚠️ This document does not appear to be a contract, policy, or legal agreement. The file may be a CSV, spreadsheet, or data export. Please upload a valid contract, agreement, or policy document for compliance auditing."
        }
    
    parties = get_party_labels(doc_type)
    
    # Step 3: Pre-detect structural issues (blank fields, missing sigs, PII)
    issues = detect_document_issues(document_text)
    
    # Step 4: Build type‑specific prompt
    prompt = build_plan_prompt(document_text, doc_type, parties, issues)
    
    # Step 5: Get plan from LLM
    plan = []
    try:
        response = llm.generate(prompt, json_mode=True)
        result = json.loads(response)
        if isinstance(result, dict) and isinstance(result.get("plan"), list):
            plan = [
                str(item).strip()
                for item in result["plan"]
                if str(item).strip()
            ][:6]
    except Exception:
        pass
    
    # Fallback: if LLM fails, use a type‑appropriate default
    if not plan:
        plan = _get_fallback_plan(doc_type, parties)
    
    return {
        "plan": plan,
        "document_type": doc_type.value,
        "pre_detected_issues": issues,
    }


def _get_fallback_plan(doc_type: ContractType, parties: dict) -> list:
    """Deterministic fallback plans per contract type."""
    fallbacks = {
        ContractType.CONSUMER_LOAN: [
            "Verify interest rate against NY usury caps (16% civil, 25% criminal) and calculate effective APR",
            "Confirm the financed asset/collateral is clearly described (UCC 2-201)",
            "Inspect document for exposed borrower PII (SSN, DOB, address)",
            "Validate repossession clause complies with UCC 9-611 written notice requirements",
            "Check prepayment penalty, late fee, and acceleration clause enforceability",
            "Verify Truth in Lending Act disclosures are present and accurate",
        ],
        ContractType.EMPLOYMENT: [
            "Check working hours, overtime, and break compliance with FLSA",
            "Verify leave entitlements and accrual rates",
            "Assess termination notice period and severance obligations",
            "Review employee liability, indemnification, and insurance requirements",
            "Evaluate non-compete and confidentiality scope for reasonableness",
            "Verify dispute resolution clause fairness and governing law applicability",
        ],
        ContractType.NDA: [
            "Verify definition of 'confidential information' is specific and reasonable",
            "Check duration and survival of confidentiality obligations",
            "Assess exclusions and carve‑outs from confidential treatment",
            "Review obligations for return/destruction of materials",
            "Evaluate remedies for breach (injunctive relief, liquidated damages)",
        ],
        ContractType.STUDENT_LOAN: [
            "Verify TILA and Higher Education Act disclosures",
            "Check APR, finance charge, and payment schedule accuracy",
            "Assess deferment, forbearance, and discharge provisions",
            "Review prepayment and consolidation rights",
            "Validate co‑signer release conditions (if applicable)",
        ],
        ContractType.LEASE: [
            "Verify security deposit amount and return timeline per state law",
            "Check maintenance and repair responsibility allocation",
            "Assess eviction notice and cure period requirements",
            "Review rent increase caps and notice requirements",
            "Evaluate subletting and assignment restrictions",
        ],
        ContractType.SERVICE_AGREEMENT: [
            "Verify scope of work and deliverables are clearly defined",
            "Check payment terms including milestones and invoice schedule",
            "Assess limitation of liability and indemnification balance",
            "Review termination for convenience and cause provisions",
            "Verify independent contractor classification language",
            "Evaluate IP ownership, insurance requirements, and governing law",
        ],
        ContractType.OTHER: [
            "Identify ambiguous or undefined material terms",
            "Verify consideration, offer, and acceptance elements are present",
            "Assess termination rights and default remedies",
            "Review dispute resolution clause for fairness",
            "Flag missing signatures, dates, or party identification",
            "Check for contradictory clauses or internal inconsistencies",
        ],
    }
    return fallbacks.get(doc_type, fallbacks[ContractType.OTHER])