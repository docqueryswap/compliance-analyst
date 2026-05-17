import json
import re
import logging
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)
llm = None


def _get_llm():
    global llm
    if llm is None:
        llm = LLMClient()
    return llm


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


KNOWN_VALID_CITATIONS_BY_TYPE = {
    "consumer_loan": [
        "Truth in Lending Act (TILA) / Regulation Z for APR, finance charge, payment schedule, and disclosure duties",
        "State usury law, including New York's 16% civil usury and 25% criminal usury thresholds where NY law applies",
        "UCC Article 9, including UCC 9-611, for security interests, collateral, repossession, and notice before disposition",
        "GLBA/privacy principles for exposed borrower PII",
    ],
    "student_loan": [
        "Truth in Lending Act (TILA) / Regulation Z for private education loan disclosures",
        "Higher Education Act for federal student-loan program disclosures and borrower rights",
    ],
    "employment": [
        "FLSA for wage, overtime, and working-hours issues",
        "FMLA and state leave laws for protected leave",
        "Title VII / EEOC frameworks for discrimination, harassment, and retaliation issues",
        "State wage-payment and termination-notice laws where applicable",
    ],
    "service_agreement": [
        "Commercial contract law for scope, payment, warranty, indemnity, termination, and limitation-of-liability terms",
        "UCC principles only where goods, warranties, or mixed goods/services are actually implicated",
        "Data protection laws only where the agreement processes personal data",
        "IP ownership / work-product principles for deliverables",
    ],
    "nda": [
        "Defend Trade Secrets Act (DTSA)",
        "Uniform Trade Secrets Act (UTSA) or state trade-secret law",
        "Common-law confidentiality and equitable relief principles",
    ],
    "lease": [
        "State landlord-tenant law for security deposits, habitability, maintenance, eviction, and notice requirements",
        "Local rent-control or rent-stabilization rules only where the jurisdiction supports them",
    ],
    "other": [
        "General contract-law principles for formation, ambiguity, breach, remedies, governing law, and dispute resolution",
    ],
}


MISAPPLIED_CITATION_PATTERNS_BY_TYPE = {
    "consumer_loan": [
        r"\btila\b.*\b(usury|interest\s+rate\s+cap|rate\s+cap|16%|25%)",
        r"\b(flsa|fmla|eeoc|title\s+vii|overtime|leave\s+entitlement|working\s+hours)\b",
    ],
    "service_agreement": [
        r"\b(usury|tila|regulation\s+z|borrower|lender|flsa|fmla|overtime|leave\s+entitlement)\b",
    ],
    "employment": [
        r"\b(usury|tila|regulation\s+z|ucc\s+9-611|repossession|borrower|lender)\b",
    ],
    "nda": [
        r"\b(usury|tila|flsa|fmla|security\s+deposit|eviction)\b",
    ],
    "lease": [
        r"\b(usury|tila|flsa|fmla|borrower|lender)\b",
    ],
    "student_loan": [
        r"\b(flsa|fmla|employment|security\s+deposit|eviction)\b",
    ],
    "other": [],
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
    
    if "lender" in report_lower and "borrower" in report_lower:
        return "consumer_loan"
    if "employee" in report_lower and "employer" in report_lower:
        return "employment"
    if "vendor" in report_lower or "service provider" in report_lower:
        return "service_agreement"
    
    return "other"


def _safe_str(val) -> str:
    """Convert any value to a string safely."""
    try:
        return str(val).strip()
    except Exception:
        return ""


def _has_actionable_critique(critique: str) -> bool:
    """Return true when critique text describes errors that need correction."""
    text = _safe_str(critique)
    if not text:
        return False
    lowered = text.lower()
    return (
        "no critical errors" not in lowered
        and "source-grounded verification" not in lowered
    )


def _known_valid_citations_for_prompt(doc_type: str) -> str:
    citations = KNOWN_VALID_CITATIONS_BY_TYPE.get(
        doc_type,
        KNOWN_VALID_CITATIONS_BY_TYPE["other"],
    )
    return "; ".join(citations)


def _critique_item_is_false_positive(item: dict, doc_type: str) -> bool:
    """Drop framework critiques that merely object to a known-valid citation."""
    if not isinstance(item, dict):
        return False

    error_text = _safe_str(item.get("error", item.get("type", ""))).lower()
    if "wrong legal framework" not in error_text:
        return False

    detail = " ".join(
        _safe_str(item.get(key, ""))
        for key in ("quote", "detail", "reason", "explanation")
    ).lower()
    if not detail:
        return False

    for pattern in MISAPPLIED_CITATION_PATTERNS_BY_TYPE.get(doc_type, []):
        if re.search(pattern, detail):
            return False

    known_terms = " ".join(
        KNOWN_VALID_CITATIONS_BY_TYPE.get(
            doc_type,
            KNOWN_VALID_CITATIONS_BY_TYPE["other"],
        )
    ).lower()
    return any(token in known_terms and token in detail for token in _tokenize_for_citation_match(detail))


def _tokenize_for_citation_match(text: str) -> list:
    candidates = [
        "tila", "truth in lending", "regulation z", "ucc", "ucc 9-611",
        "uniform commercial code", "usury", "flsa", "fmla", "title vii",
        "eeoc", "dtsa", "utsa", "trade secret", "landlord", "tenant",
        "security deposit", "higher education act", "commercial contract",
    ]
    lowered = text.lower()
    return [candidate for candidate in candidates if candidate in lowered]


def _dedupe_repeated_sections(report: str) -> str:
    """Remove repeated markdown sections while preserving the first occurrence."""
    text = _safe_str(report)
    if not text:
        return ""

    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    if not matches:
        return text

    parts = []
    prefix = text[:matches[0].start()].strip()
    if prefix:
        parts.append(prefix)

    seen = set()
    for index, match in enumerate(matches):
        section_start = match.start()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading_key = re.sub(r"[^a-z0-9]+", " ", match.group(1).lower()).strip()
        if heading_key in seen:
            continue
        seen.add(heading_key)
        section = text[section_start:section_end].strip()
        if section:
            parts.append(section)

    return "\n\n".join(parts).strip()


def critic_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    draft = state.get("draft_report", "")
    doc_type = state.get("document_type", "other")
    valid_citations = _known_valid_citations_for_prompt(doc_type)

    prompt = f"""Validate this compliance report. Do not re-audit from scratch.

Document type: {doc_type}. Never change it.

Known-valid references for this type: {valid_citations}
Do not flag these citations just because they appear. Flag them only when the report applies them to the wrong duty or party.

Flag only factual report errors:
- HALLUCINATION: facts/clauses/citations not in source
- WRONG LEGAL FRAMEWORK
- WRONG PARTY BLAMED
- SEVERITY INCONSISTENCY
- VAGUE RECOMMENDATIONS
- CONTRADICTION

Type rules:
- service_agreement: mutual liability caps are standard; flagging them is an error.
- consumer_loan: usury caps are state law, not TILA.
- employment: do not apply lending/commercial frameworks.

YOU MUST VERIFY EVERY CLAIM in the report against the source excerpt:
1. Is each clause/section reference actually IN the source?
2. Is each legal citation appropriate for this document type?
3. Are severity ratings consistent for the same clause everywhere?
4. Are recommendations specific or vague?

If the report is flawless, return passes_validation=true and critique=[].
If you find ANY error, return passes_validation=false with specific critique items.
NEVER return empty critique without checking — actually read the report.

Return ONLY valid JSON:
{{"passes_validation": true, "critique": [], "confidence_score": 90, "missing_risks": []}}

Source excerpt:
{str(context)[:900]}

Draft report:
{draft[:1500]}

JSON:"""

    final_report = draft
    critique = ""
    passes = False
    confidence_score = 40
    missing_risks = []
    result = {}
    fallback_triggered = False

    for attempt in range(3):
        response = _get_llm().generate(
            prompt,
            json_mode=True,
            max_tokens=3072,
            use_reasoning=True
        )
        logger.info(f"Critic raw response (attempt {attempt+1}, first 500 chars): {response[:500]}")
        result = _extract_json(response)
        if result:
            break
    else:
        logger.warning("All attempts to get valid JSON from critic failed. Using conservative fallback.")
        result = {}

    if result and "error" in result and not any(
        key in result for key in ("passes_validation", "critique", "confidence_score", "missing_risks")
    ):
        logger.warning("Critic LLM returned an error object. Using conservative fallback.")
        result = {}

    if not result:
        fallback_triggered = True
        logger.warning("Critic fallback triggered — final report is unchanged draft.")
        result = {
            "passes_validation": False,
            "critique": _generate_fallback_critique(draft, doc_type),
            "confidence_score": 40,
            "missing_risks": [],
        }

    passes = bool(result.get("passes_validation", False))
    critique_raw = result.get("critique", "")
    if isinstance(critique_raw, list):
        critique_parts = []
        for item in critique_raw:
            try:
                if isinstance(item, dict):
                    if _critique_item_is_false_positive(item, doc_type):
                        logger.info("Dropped false-positive framework critique for doc_type=%s: %s", doc_type, item)
                        continue
                    err = item.get("error", "")
                    if not err or not err.strip():
                        continue
                    q = item.get("quote", "")
                    line = f"- {err}"
                    if q:
                        line += f"\n  Quote: {q}"
                    critique_parts.append(line)
                elif isinstance(item, str):
                    critique_parts.append(f"- {item}")
            except Exception:
                critique_parts.append("- [unparseable critique item]")
        critique = "\n".join(critique_parts)
    elif isinstance(critique_raw, str):
        critique = critique_raw.strip()
    else:
        critique = ""

    errors_found = _has_actionable_critique(critique)

    confidence_score = result.get("confidence_score", 40)
    missing_risks_raw = result.get("missing_risks", [])

    if not critique:
        critique = _generate_fallback_critique(draft, doc_type) if fallback_triggered else "No critical errors found."
        errors_found = _has_actionable_critique(critique)

    if not isinstance(missing_risks_raw, list):
        missing_risks_raw = []
    missing_risks = []
    for item in missing_risks_raw:
        try:
            if isinstance(item, dict):
                risk_text = _safe_str(item.get("risk", item.get("error", item.get("detail", ""))))
                if risk_text:
                    missing_risks.append(risk_text)
            elif isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    missing_risks.append(stripped)
            elif item is not None:
                s = _safe_str(item)
                if s:
                    missing_risks.append(s)
        except Exception:
            continue

    try:
        confidence_score = int(confidence_score)
    except (TypeError, ValueError):
        confidence_score = 40
    confidence_score = max(0, min(100, confidence_score))

    error_count = 0
    if errors_found:
        for err_type in ["HALLUCINATION", "WRONG LEGAL FRAMEWORK", "WRONG PARTY BLAMED",
                         "SEVERITY INCONSISTENCY", "VAGUE RECOMMENDATIONS", "CONTRADICTION"]:
            if err_type in critique.upper():
                error_count += 1
    risk_count = len(missing_risks)

    if fallback_triggered:
        confidence_score = min(confidence_score, 45)
    else:
        penalty = min(error_count * 12, 48) + min(risk_count * 6, 18)
        if errors_found or risk_count:
            confidence_score = min(confidence_score, 88) if confidence_score else 88
            confidence_score = max(35, confidence_score - penalty)
        else:
            confidence_score = max(confidence_score, 90)

    # Consistency guard
    if errors_found or missing_risks:
        passes = False
    elif not fallback_triggered:
        passes = True
    if passes and confidence_score < 60:
        passes = False
        critique = (critique or "") + "\nValidation overridden: confidence score too low to certify report."

    effective_doc_type = doc_type
    if doc_type == "other":
        detected = _detect_doc_type_from_report(final_report)
        if detected != "other":
            effective_doc_type = detected

    try:
        final_report = _inject_missing_risks(final_report, missing_risks, effective_doc_type)
    except Exception as e:
        logger.error(f"_inject_missing_risks failed: {e}")

    if errors_found and "Corrections Required (Critic-Identified)" not in _safe_str(final_report):
        corrections = "\n\n## ⚠️ Corrections Required (Critic-Identified)\n"
        corrections += "The following issues were flagged. Report body preserved for human review:\n\n"
        corrections += critique + "\n"
        final_report = corrections + _safe_str(final_report or draft)

    final_report = _dedupe_repeated_sections(final_report or draft)

    return {
        "passes_validation": passes,
        "critique": critique,
        "final_report": final_report,
        "confidence_score": confidence_score,
        "missing_risks": missing_risks,
        "_fallback_triggered": fallback_triggered,
    }