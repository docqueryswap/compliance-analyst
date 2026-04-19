import json
import re
from core.llm_client import LLMClient

llm = LLMClient()


def critic_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    draft = state.get("draft_report", "")

    prompt = f"""Review this draft report. Return JSON with:
- "passes_validation": true/false
- "feedback": detailed critique
- "final_report": improved report

Plan: {plan}
Context: {str(context)[:800]}
Draft: {draft}"""

    response = llm.generate(prompt, json_mode=True)

    # Parse
    result = {}
    try:
        result = json.loads(response)
    except:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except:
                pass

    return {
        "passes_validation": result.get("passes_validation", True),
        "critique": result.get("feedback", ""),
        "final_report": result.get("final_report", draft),
    }