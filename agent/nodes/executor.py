from core.llm_client import LLMClient

llm = LLMClient()


def executor_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    doc_type = state.get("document_type", "other")
    document_text = state.get("document_text", "")

    context_str = "\n\n".join(context[:10]) if context else "No additional context."
    document_excerpt = document_text[:5000]

    prompt = f"""You are a senior compliance analyst preparing a production-quality compliance risk assessment.
Only make findings that are supported by the document excerpt or retrieved context.
If evidence is weak, say so explicitly instead of overstating.
Prioritize legal risk, employee-unfavorable terms, enforceability issues, and business impact.

Plan: {plan}
Document type: {doc_type}
Source document excerpt:
{document_excerpt}

Retrieved context:
{context_str}

Write a structured professional report with the following sections exactly:
## Executive Summary
## High Risk Clauses
## Compliance Violations
## Business Impact
## Risk Severity
## Recommended Actions
## Confidence Score

Requirements:
- Quote or paraphrase the specific clause behavior when possible.
- Flag missing evidence where conclusions are uncertain.
- Call out unfair termination, salary, benefits, liability, indemnity, confidentiality, privacy, and dispute-resolution issues when relevant.
- Use Low / Medium / High severity labels.
- Recommended Actions must be prioritized, clause-level, and concrete.
- Each recommendation should say what contractual or policy language should be added, replaced, capped, clarified, or removed.
- Use jurisdiction-aware legal phrasing safely:
  * good: "likely conflicts with working-hours or leave-entitlement obligations under applicable labor law"
  * good: "may create risk under employee data protection obligations"
  * good: "may be vulnerable to challenge under unfair contract or enforceability principles"
  * avoid unsupported country-specific statute names unless the document or context clearly identifies the jurisdiction
- Avoid vague recommendations such as:
  * "review and update policy"
  * "improve termination process"
  * "review liability clause"
- Prefer strong remediation language such as:
  * "add a mandatory employer termination notice period of at least 30 days, subject to applicable law"
  * "add a statutory paid leave clause aligned with minimum leave-entitlement obligations under applicable labor law"
  * "replace unlimited employee liability with a proportionate and clearly capped liability clause"
  * "add explicit employee consent and lawful-basis language before third-party data sharing"
  * "add an overtime compensation clause for work beyond lawful working-hour thresholds"
  * "replace one-sided dispute jurisdiction wording with neutral dispute-resolution language"
- Confidence Score must reflect evidentiary support, specificity of clause analysis, and whether recommendations are legally precise.
- In the Recommended Actions section, use numbered actions and tie each action to a corresponding risk.

Draft Report:"""

    draft = llm.generate(prompt, max_tokens=1800)
    return {"draft_report": draft}
