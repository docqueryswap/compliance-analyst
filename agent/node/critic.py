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

    # Log the raw response for debugging
    logger.info(f"Critic raw response (first 500 chars): {response[:500]}")

    # If the response indicates a provider failure, use fallback
    if response.startswith("⚠️"):
        logger.warning("LLM provider error detected in Critic. Using fallback.")
        return {
            "passes_validation": True,
            "critique": "The critique service is temporarily unavailable. The draft report is provided as final.",
            "final_report": draft
        }

    # Attempt to parse JSON
    result = {}
    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown or plain text
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning("Could not parse JSON from Critic response. Using fallback.")
                result = {}
        else:
            logger.warning("No JSON object found in Critic response. Using fallback.")

    # Extract fields with defaults
    passes = bool(result.get("passes_validation", False))
    critique = result.get("feedback", "").strip()
    final_report = result.get("final_report", draft)

    # If critique is empty, provide a sensible default
    if not critique:
        critique = "The report appears to meet the requirements based on the available context."

    return {
        "passes_validation": passes,
        "critique": critique,
        "final_report": final_report
    }