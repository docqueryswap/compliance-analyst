import json
import re
import logging
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)
llm = LLMClient()


def _extract_json(text: str) -> dict:
    """Robust JSON extraction from LLM output."""
    if not text:
        return {}
    cleaned = text.strip()
    # Remove markdown fences
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


def _generate_fallback_critique(draft: str) -> str:
    draft_lower = draft.lower()
    if "executive summary" in draft_lower and "recommended actions" in draft_lower:
        return "The report is structured well, but it still requires a source-grounded check for unsupported conclusions and missing compliance risks."
    elif "executive summary" in draft_lower:
        return "The report has some structure but should strengthen the evidence basis, risk prioritization, and remediation steps."
    elif len(draft) < 500:
        return "The report is too brief for a reliable compliance assessment and may omit material risks or support."
    else:
        return "The report addresses the topic at a high level, but a stricter validation of evidence, missing risks, and recommendation quality is still needed."


def _recommendation_for_risk(risk: str) -> str:
    risk_lower = risk.lower()
    if "leave" in risk_lower:
        return "Add a statutory paid leave clause aligned with minimum leave-entitlement obligations under applicable labor law, including accrual, approval, and carry-forward treatment where required."
    if "liability" in risk_lower or "indemn" in risk_lower:
        return "Replace any unlimited or one-sided employee liability wording with a proportionate, clearly capped liability and indemnity clause tied to legally permissible loss categories."
    if "termination" in risk_lower or "notice" in risk_lower:
        return "Add a mandatory employer termination notice period of at least 30 days, or the higher period required by applicable law, and define termination-for-cause versus termination-without-cause standards."
    if "salary" in risk_lower or "wage" in risk_lower or "overtime" in risk_lower:
        return "Add express wage, overtime, and payment-timing language aligned with applicable working-hours and compensation obligations, including compensation for work beyond lawful limits."
    if "data" in risk_lower or "privacy" in risk_lower or "consent" in risk_lower:
        return "Add explicit employee notice, lawful-basis, and consent language before any third-party data sharing, together with purpose limitation and retention controls."
    if "dispute" in risk_lower or "jurisdiction" in risk_lower or "arbitration" in risk_lower:
        return "Replace one-sided dispute jurisdiction wording with balanced dispute-resolution language that is more likely to remain enforceable under applicable contract-law principles."
    if "confidential" in risk_lower:
        return "Clarify confidentiality obligations with defined scope, permitted disclosures, survival period, and carve-outs for legally protected whistleblowing or statutory reporting."
    if "non-compete" in risk_lower or "restraint" in risk_lower:
        return "Narrow any restrictive covenant by scope, duration, geography, and legitimate business interest so it is less likely to be challenged as overbroad or unenforceable."
    return f"Revise the clause-level wording for {risk_lower} so the obligation is balanced, operationally clear, and less vulnerable under applicable labor, privacy, or unfair-contract principles."


def _adjust_confidence_score(confidence_score: int, critique: str, missing_risks: list, final_report: str) -> int:
    adjusted = confidence_score
    critique_lower = critique.lower()
    report_lower = final_report.lower()

    adjusted -= min(len(missing_risks) * 8, 24)

    penalty_markers = [
        "unsupported",
        "hallucinated",
        "contradiction",
        "missing evidence",
        "weak recommendation",
        "omitted risk",
    ]
    adjusted -= sum(6 for marker in penalty_markers if marker in critique_lower)

    if "## confidence score" not in report_lower:
        adjusted -= 10
    if "## recommended actions" not in report_lower:
        adjusted -= 10
    if "likely conflicts with" in report_lower or "may create risk under" in report_lower or "may be vulnerable to challenge under" in report_lower:
        adjusted += 4

    return max(0, min(adjusted, 100))


def _inject_missing_risks(final_report: str, missing_risks: list) -> str:
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
        f"- {_recommendation_for_risk(risk)}"
        for risk in risks_to_add
    )

    if "## Compliance Violations" in updated_report:
        updated_report = updated_report.replace(
            "## Compliance Violations",
            "## Compliance Violations\n"
            "Additional critic-identified risks that require inclusion:\n"
            f"{risk_lines}\n",
            1,
        )
    else:
        updated_report = (
            f"{updated_report}\n\n## Compliance Violations\n"
            "Additional critic-identified risks that require inclusion:\n"
            f"{risk_lines}"
        ).strip()

    if "## Recommended Actions" in updated_report:
        updated_report = updated_report.replace(
            "## Recommended Actions",
            "## Recommended Actions\n"
            "Prioritized remediation for critic-identified gaps:\n"
            f"{action_lines}\n",
            1,
        )
    else:
        updated_report = (
            f"{updated_report}\n\n## Recommended Actions\n"
            "Prioritized remediation for critic-identified gaps:\n"
            f"{action_lines}"
        ).strip()

    return updated_report


def critic_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    draft = state.get("draft_report", "")

    prompt = f"""You are a strict compliance reviewer validating a draft audit report.
Your job is to reject weak, hallucinated, unsupported, incomplete, or internally inconsistent analysis.

You MUST output ONLY a valid JSON object with exactly these five keys:
- "passes_validation": true or false
- "critique": a detailed critique explaining unsupported claims, missing evidence, weak recommendations, contradictions, or omitted risks
- "final_report": the improved report as plain text
- "confidence_score": an integer from 0 to 100 based on evidentiary support and report reliability
- "missing_risks": an array of short strings for critical risks the draft missed

Validation rules:
- Detect hallucinated findings not supported by the document/context.
- Detect unsupported claims and vague recommendations.
- Detect missing critical compliance risks.
- Detect contradiction with retrieved context.
- Strengthen severity labeling and business impact discussion.
- Preserve only well-supported findings.
- If you identify missing risks such as leave policy gaps, liability clauses, wage/termination issues, or unfair obligations, you must add them into "final_report" itself, not only into "critique" or "missing_risks".
- The "final_report" must be a repaired report that already incorporates the missing risks into the relevant sections.
- Replace vague recommendations with specific clause-level remediation language.
- Use careful jurisdiction-aware legal phrasing such as:
  * "likely conflicts with working-hours or leave-entitlement obligations under applicable labor law"
  * "may create risk under employee data protection obligations"
  * "may be vulnerable to challenge under unfair contract principles"
- Do not cite a country-specific law unless the document or context clearly supports it.
- The Recommended Actions section must read like a compliance consultant deliverable, with concrete drafting fixes rather than generic advice.

Plan: {plan}
Context (excerpt): {str(context)[:2500]}
Draft: {draft}

JSON:"""

    # Try up to 2 times
    for attempt in range(2):
        response = llm.generate(prompt, json_mode=True)
        logger.info(f"Critic raw response (attempt {attempt+1}, first 500 chars): {response[:500]}")
        result = _extract_json(response)
        if result:
            break
    else:
        logger.warning("All attempts to get valid JSON failed. Using fallback.")
        result = {}

    if not result:
        result = {
            "passes_validation": True,
            "critique": _generate_fallback_critique(draft),
            "final_report": draft,
            "confidence_score": 55,
            "missing_risks": [],
        }

    passes = bool(result.get("passes_validation", True))
    critique = result.get("critique", "").strip()
    final_report = result.get("final_report", draft)
    confidence_score = result.get("confidence_score", 55)
    missing_risks = result.get("missing_risks", [])

    if not critique:
        critique = _generate_fallback_critique(draft)

    if not isinstance(missing_risks, list):
        missing_risks = []
    missing_risks = [str(item).strip() for item in missing_risks if str(item).strip()]

    try:
        confidence_score = int(confidence_score)
    except (TypeError, ValueError):
        confidence_score = 55
    final_report = _inject_missing_risks(final_report, missing_risks)
    confidence_score = _adjust_confidence_score(confidence_score, critique, missing_risks, final_report)

    return {
        "passes_validation": passes,
        "critique": critique,
        "final_report": final_report,
        "confidence_score": confidence_score,
        "missing_risks": missing_risks,
    }
