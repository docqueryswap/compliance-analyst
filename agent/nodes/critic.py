import json
import re
import logging
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)
llm = LLMClient()


# Domain-aware recommendation templates
RECOMMENDATIONS_BY_TYPE = {
    "consumer_loan": {
        "usury": "Replace the variable interest rate with a fixed APR below the applicable state usury cap (16% civil in NY) or cap CPI adjustments so the effective rate never exceeds the cap.",
        "collateral": "Define the financed asset with specific identifying details (make, model, VIN/serial number) in the preamble.",
        "pii": "Redact all PII (SSN, DOB) from the document and store separately in encrypted format with access controls.",
        "repossession": "Add a mandatory 30-day written notice of default and opportunity to cure before repossession per UCC 9-611.",
        "prepayment": "Add a clear prepayment clause stating whether penalties apply and at what rate.",
        "tila": "Include a TILA disclosure box with APR, finance charge, total of payments, and payment schedule.",
        "default": "Replace vague penalty language with specific, quantifiable charges that comply with state usury and UCC requirements.",
        "termination": "Clarify termination triggers, notice requirements, and post-termination obligations including collateral disposition.",
    },
    "employment": {
        "leave": "Add a statutory paid leave clause aligned with minimum leave-entitlement obligations under applicable labor law.",
        "liability": "Replace any unlimited or one-sided employee liability wording with a proportionate, clearly capped liability clause.",
        "termination": "Add a mandatory employer termination notice period of at least 30 days or the higher period required by applicable law.",
        "salary": "Add express wage, overtime, and payment-timing language aligned with applicable working-hours and compensation obligations.",
        "overtime": "Add an overtime compensation clause for work beyond lawful working-hour thresholds.",
        "data": "Add explicit employee notice, lawful-basis, and consent language before any third-party data sharing.",
        "dispute": "Replace one-sided dispute jurisdiction wording with balanced dispute-resolution language.",
        "confidential": "Clarify confidentiality obligations with defined scope, permitted disclosures, and survival period.",
        "non-compete": "Narrow restrictive covenant by scope, duration, geography, and legitimate business interest.",
        "default": "Revise the clause to be balanced, operationally clear, and compliant with applicable employment law.",
    },
    "service_agreement": {
        "scope": "Define deliverables with specific quantities, deadlines, and acceptance criteria in the scope of engagement section.",
        "payment": "Add a clear payment schedule with milestone-based payments, invoice deadlines, and late fee provisions.",
        "liability": "Ensure the limitation of liability is MUTUAL. Mutual caps on consequential damages are standard and protective — do not flag as violations.",
        "termination": "Specify the number of days for termination notice (30 days is standard) and define post-termination payment deadlines.",
        "ip": "Add a clear IP ownership clause specifying that work product belongs to Client upon full payment.",
        "insurance": "Specify minimum insurance coverage amounts (general liability: $1M, professional liability: $2M, workers' compensation: statutory).",
        "governing_law": "Fill in the governing law and jurisdiction blanks with the agreed state and venue.",
        "dispute": "Specify the dispute resolution method (arbitration/mediation/negotiation) and the governing rules.",
        "indemnity": "Ensure indemnification obligations are mutual and tied to the indemnifying party's negligence or breach.",
        "blank_fields": "Complete all blank fields with specific, agreed-upon terms before execution.",
        "default": "Add specific, measurable language to replace vague or incomplete provisions.",
    },
    "nda": {
        "definition": "Narrow the definition of confidential information to specific categories with clear exclusions.",
        "duration": "Specify a reasonable duration for confidentiality obligations (3-5 years is standard for commercial NDAs).",
        "return": "Add clear obligations for return or destruction of confidential materials upon termination.",
        "default": "Clarify the scope and duration of obligations to ensure enforceability.",
    },
    "student_loan": {
        "disclosure": "Add required TILA and Higher Education Act disclosures including APR and total cost of borrowing.",
        "deferment": "Clearly outline deferment, forbearance, and income-driven repayment options.",
        "prepayment": "State whether prepayment penalties apply and provide clear consolidation rights.",
        "default": "Ensure all federally required disclosures are present and accurately calculated.",
    },
    "lease": {
        "deposit": "Specify security deposit amount and return timeline in compliance with state law (typically 14-30 days).",
        "maintenance": "Clearly allocate maintenance and repair responsibilities between landlord and tenant.",
        "eviction": "Add specific notice and cure periods before eviction proceedings can begin.",
        "default": "Ensure terms comply with applicable landlord-tenant laws in the governing jurisdiction.",
    },
    "other": {
        "ambiguity": "Replace ambiguous terms with specific, measurable definitions tied to objective criteria.",
        "termination": "Add clear notice periods (e.g., 30 days), cure periods, and post-termination payment obligations.",
        "dispute": "Specify governing law, jurisdiction, and a neutral dispute resolution method (e.g., binding arbitration).",
        "signatures": "Ensure all parties sign and date the agreement for enforceability.",
        "blank_fields": "Complete all blank fields with specific, agreed-upon terms before execution.",
        "default": "Replace vague language with specific, enforceable provisions that leave no material terms open.",
    },
}


def _extract_json(text: str) -> dict:
    """Robust JSON extraction from LLM output."""
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _generate_fallback_critique(draft: str, doc_type: str) -> str:
    draft_lower = draft.lower()
    if "executive summary" in draft_lower and "recommended actions" in draft_lower:
        return f"The report is structured but requires source-grounded verification for unsupported conclusions and {doc_type}-specific compliance risks. A human reviewer should validate legal citations."
    elif len(draft) < 500:
        return "The report is too brief for a reliable compliance assessment and likely omits material risks and supporting evidence."
    else:
        return "The report addresses the topic at a high level, but stricter validation of evidence, missing risks, and recommendation specificity is needed before finalization."


def _get_recommendation(doc_type: str, risk_text: str) -> str:
    """Get a type-appropriate, specific recommendation for a given risk text."""
    recs = RECOMMENDATIONS_BY_TYPE.get(doc_type, RECOMMENDATIONS_BY_TYPE["other"])
    risk_lower = risk_text.lower()
    
    for keyword, recommendation in recs.items():
        if keyword in risk_lower:
            return recommendation
    
    return recs["default"]


def _inject_missing_risks(final_report: str, missing_risks: list, doc_type: str) -> str:
    """Inject critic-identified missing risks into the report with type-specific recommendations."""
    cleaned_risks = [str(item).strip() for item in missing_risks if str(item).strip()]
    if not cleaned_risks:
        return final_report

    updated_report = final_report.strip() if final_report else ""
    report_lower = updated_report.lower()
    risks_to_add = [
        risk for risk in cleaned_risks
        if risk.lower() not in report_lower
    ]
    if not risks_to_add:
        return updated_report

    risk_lines = "\n".join(f"- {risk}" for risk in risks_to_add)
    action_lines = "\n".join(
        f"- {_get_recommendation(doc_type, risk)}"
        for risk in risks_to_add
    )

    if "## Compliance Violations" in updated_report:
        updated_report = updated_report.replace(
            "## Compliance Violations",
            "## Compliance Violations\n"
            "Additional critic-identified risks:\n"
            f"{risk_lines}\n",
            1,
        )
    else:
        updated_report = (
            f"{updated_report}\n\n## Compliance Violations\n"
            "Additional critic-identified risks:\n"
            f"{risk_lines}"
        ).strip()

    if "## Recommended Actions" in updated_report:
        updated_report = updated_report.replace(
            "## Recommended Actions",
            "## Recommended Actions\n"
            "Prioritized remediation for identified gaps:\n"
            f"{action_lines}\n",
            1,
        )
    else:
        updated_report = (
            f"{updated_report}\n\n## Recommended Actions\n"
            "Prioritized remediation for identified gaps:\n"
            f"{action_lines}"
        ).strip()

    return updated_report


def _detect_doc_type_from_report(report: str) -> str:
    """Try to extract the document type from the report text, falling back to 'other'."""
    report_lower = report.lower()
    
    # Check Executive Summary for document type
    type_patterns = [
        (r"document type:\s*consumer\s*loan", "consumer_loan"),
        (r"document type:\s*student\s*loan", "student_loan"),
        (r"document type:\s*employment", "employment"),
        (r"document type:\s*nda|non-disclosure", "nda"),
        (r"document type:\s*lease", "lease"),
        (r"document type:\s*(vendor|service)\s*(agreement|contract)", "service_agreement"),
    ]
    
    for pattern, doc_type in type_patterns:
        if re.search(pattern, report_lower):
            return doc_type
    
    # Fallback: check for strong indicators in the report
    if "lender" in report_lower and "borrower" in report_lower:
        return "consumer_loan"
    if "employee" in report_lower and "employer" in report_lower:
        return "employment"
    if "vendor" in report_lower or "service provider" in report_lower:
        return "service_agreement"
    
    return "other"


def critic_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    draft = state.get("draft_report", "")
    doc_type = state.get("document_type", "other")

    prompt = f"""You are a strict compliance reviewer VALIDATING a draft audit report.
Your job is to CATCH ERRORS in the report, not to re-audit the document from scratch.

THE DOCUMENT TYPE IS: {doc_type}
DO NOT CHANGE THE DOCUMENT TYPE. The classifier already determined this and it is authoritative.

VALIDATION RULES — flag these as errors:
1. HALLUCINATION: Does the report reference clauses, sections, numbers, or facts NOT present in the source document? Flag them specifically.
2. WRONG LEGAL FRAMEWORK: Does the report apply incorrect laws? (e.g., citing TILA for usury caps when state law applies; using employment law on a non-employment contract)
3. WRONG PARTY BLAMED: Are compliance obligations attributed to the wrong party? (e.g., blaming borrower for lender's TILA disclosure duties)
4. SEVERITY INCONSISTENCY: Does the same clause get different severity ratings in different parts of the report?
5. VAGUE RECOMMENDATIONS: Are recommendations generic ("review and update") instead of specific (exact clause language to change)?
6. CONTRADICTION: Does the report contradict itself or the source document?

CRITICAL — DO NOT DO THESE:
- DO NOT change the document type from "{doc_type}".
- DO NOT re-analyze the document. You are VALIDATING the report, not writing a new one.
- DO NOT make subjective legal judgments (e.g., "14.4% is fine"). Only flag factual errors.
- DO NOT invent missing risks that aren't clearly visible in the document text provided.

TYPE-SPECIFIC RULES:
- If doc_type is "service_agreement": Mutual limitation of liability clauses are STANDARD and NOT violations. If the report flags a mutual liability cap as a risk, mark it as an ERROR.
- If doc_type is "consumer_loan": Usury caps come from STATE law (e.g., NY Gen. Oblig. Law), not TILA. TILA is about disclosure, not rate caps. Flag misattribution as an ERROR.
- If doc_type is "employment": Do not apply lending or commercial contract frameworks.

You MUST output ONLY a valid JSON object with exactly these keys:
- "passes_validation": true ONLY if report has NO hallucinations, NO wrong framework, NO contradictory severities, NO vague recommendations
- "critique": specific errors found with exact quotes from the draft. If no errors, say "No critical errors found."
- "final_report": the CORRECTED report text (fix errors, remove hallucinations, keep correct findings)
- "confidence_score": integer 0-100. Lower score = more errors found. 90+ = nearly perfect. 70-89 = minor issues. 50-69 = material errors. Below 50 = unreliable.
- "missing_risks": array of short strings ONLY for obvious risks clearly visible in the document text that the report completely missed

Source Document Excerpt: {str(context)[:2000]}
Draft Report to Validate:
{draft[:4000]}

JSON:"""

    for attempt in range(2):
        response = llm.generate(
            prompt,
            json_mode=True,
            max_tokens=3000,
            use_reasoning=True
        )
        logger.info(f"Critic raw response (attempt {attempt+1}, first 500 chars): {response[:500]}")
        result = _extract_json(response)
        if result:
            break
    else:
        logger.warning("All attempts to get valid JSON from critic failed. Using conservative fallback.")
        result = {}

    if not result:
        result = {
            "passes_validation": False,
            "critique": _generate_fallback_critique(draft, doc_type),
            "final_report": draft,
            "confidence_score": 40,
            "missing_risks": [],
        }

    passes = bool(result.get("passes_validation", False))
    critique = result.get("critique", "").strip()
    final_report = result.get("final_report", draft)
    confidence_score = result.get("confidence_score", 40)
    missing_risks = result.get("missing_risks", [])

    if not critique:
        critique = _generate_fallback_critique(draft, doc_type)

    if not isinstance(missing_risks, list):
        missing_risks = []
    missing_risks = [str(item).strip() for item in missing_risks if str(item).strip()]

    try:
        confidence_score = int(confidence_score)
    except (TypeError, ValueError):
        confidence_score = 40
    confidence_score = max(0, min(100, confidence_score))

    # Use the doc_type from the report itself if state has "other" but report says otherwise
    effective_doc_type = doc_type
    if doc_type == "other":
        detected = _detect_doc_type_from_report(final_report)
        if detected != "other":
            effective_doc_type = detected

    final_report = _inject_missing_risks(final_report, missing_risks, effective_doc_type)

    return {
        "passes_validation": passes,
        "critique": critique,
        "final_report": final_report,
        "confidence_score": confidence_score,
        "missing_risks": missing_risks,
    }