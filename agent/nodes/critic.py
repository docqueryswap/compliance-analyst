import json
import re
import logging
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)
llm = LLMClient()


def critic_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    draft = state.get("draft_report", "")

    prompt = f"""You are a meticulous compliance officer. Review the draft report against the plan and context. Output a JSON object with:
- "passes_validation": true/false
- "feedback": detailed critique (at least 2-3 sentences)
- "final_report": the improved report as plain text

Plan: {plan}
Context (excerpt): {str(context)[:800]}
Draft: {draft}

JSON:"""

    response = llm.generate(prompt, json_mode=True)
    logger.info(f"Critic raw response (first 500 chars): {response[:500]}")

    # Clean markdown fences
    cleaned = response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    result = {}
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except:
                result = {}
        else:
            result = {}

    passes = bool(result.get("passes_validation", False))
    critique = result.get("feedback", "").strip()
    final_report = result.get("final_report", draft)

    if not critique:
        critique = "The report appears to meet the requirements based on the available context."

    return {
        "passes_validation": passes,
        "critique": critique,
        "final_report": final_report
    }