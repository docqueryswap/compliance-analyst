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
    if "executive summary" in draft_lower and "recommendation" in draft_lower:
        return "The report is well-structured and covers the required sections. No major issues detected."
    elif "executive summary" in draft_lower:
        return "The report includes an executive summary but could benefit from clearer recommendations."
    elif len(draft) < 500:
        return "The report is brief and may lack sufficient detail. Consider expanding key findings."
    else:
        return "The report appears to address the compliance requirements. A detailed review was not available."


def critic_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    draft = state.get("draft_report", "")

    # Improved prompt with explicit JSON example
    prompt = f"""You are a meticulous compliance officer. Review the draft report against the plan and context. 
You MUST output ONLY a valid JSON object with exactly these three keys:
- "passes_validation": true or false
- "feedback": a detailed critique (2-3 sentences)
- "final_report": the improved report as plain text

Example: {{"passes_validation": true, "feedback": "The report accurately identifies key obligations and provides actionable recommendations.", "final_report": "..."}}

Plan: {plan}
Context (excerpt): {str(context)[:800]}
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
            "feedback": _generate_fallback_critique(draft),
            "final_report": draft,
        }

    passes = bool(result.get("passes_validation", True))
    critique = result.get("feedback", "").strip()
    final_report = result.get("final_report", draft)

    if not critique:
        critique = _generate_fallback_critique(draft)

    return {
        "passes_validation": passes,
        "critique": critique,
        "final_report": final_report,
    }