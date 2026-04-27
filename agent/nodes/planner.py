import json
from core.llm_client import LLMClient

llm = LLMClient()


DEFAULT_PLAN = [
    "Identify material legal and compliance risks in the document",
    "Detect clauses that are unfavorable to the employee or counterparty",
    "Flag labor law, wage, termination, liability, confidentiality, and dispute resolution concerns",
    "Assess enforceability, operational exposure, and business risk severity",
    "Provide prioritized remediation recommendations with practical next steps",
]

DOC_TYPE_GUIDANCE = {
    "resume": "Treat the document as an employment-related profile and focus on employment law, candidate representations, conflicts, confidentiality exposure, and hiring-risk signals.",
    "contract": "Treat the document as a binding legal agreement and focus on enforceability, liability allocation, termination rights, payment terms, non-compete, indemnity, dispute resolution, and statutory compliance.",
    "policy": "Treat the document as an internal or external policy and focus on regulatory alignment, missing controls, inconsistent obligations, employee fairness, and implementation risk.",
    "report": "Treat the document as an analytical or compliance report and focus on unsupported claims, missing material risks, regulatory exposure, and decision-making gaps.",
    "other": "Treat the document as a business or legal text and focus on contractual, regulatory, employee, and operational compliance exposure.",
}


def planner_node(state: dict) -> dict:
    document_text = state.get("document_text", "")
    guidance_text = "\n".join(
        f'- "{doc_type}": {guidance}'
        for doc_type, guidance in DOC_TYPE_GUIDANCE.items()
    )

    prompt = f"""Analyze the document excerpt and return a JSON object with:
- "document_type": exactly one of "resume", "contract", "policy", "report", "other"
- "plan": an array of 5-6 compliance-focused audit tasks tailored to the document

Return ONLY valid JSON in this shape:
{{"document_type": "contract", "plan": ["task 1", "task 2", "task 3"]}}

Document classification options:
- "resume"
- "contract"
- "policy"
- "report"
- "other"

Document-specific guidance:
{guidance_text}

Planner rules:
- Every task must be about compliance, legal risk, enforceability, employee fairness, or business exposure.
- Do NOT produce generic tasks like "Summarize document" or "Identify key points".
- Prefer tasks such as:
  * identify legal/compliance risks
  * detect employee-unfavorable clauses
  * flag labor law violations
  * check unfair termination, salary, benefits, liability, indemnity, confidentiality, and dispute clauses
  * assess enforceability and business risk
  * provide prioritized clause-level recommendations with jurisdiction-aware legal wording
- Tailor the tasks to what is actually present in the document excerpt.

Document:
{document_text[:1500]}"""

    doc_type = "other"
    plan = DEFAULT_PLAN
    try:
        response = llm.generate(prompt, json_mode=True)
        result = json.loads(response)
        if isinstance(result, dict):
            doc_type = result.get("document_type", "other")
            candidate_plan = result.get("plan", DEFAULT_PLAN)
            if isinstance(candidate_plan, list):
                filtered_plan = [
                    str(item).strip()
                    for item in candidate_plan
                    if str(item).strip()
                ]
                if filtered_plan:
                    plan = filtered_plan[:6]
        if doc_type not in {"resume", "contract", "policy", "report", "other"}:
            doc_type = "other"
    except:
        doc_type = "other"
        plan = DEFAULT_PLAN

    plan = [
        task for task in plan
        if task.lower() not in {"summarize document", "identify key points", "provide recommendations"}
    ] or DEFAULT_PLAN

    return {"plan": plan, "document_type": doc_type}
