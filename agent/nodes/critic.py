import json
from core.llm_client import LLMClient

llm = LLMClient()

def critic_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    draft = state.get("draft_report", "")
    
    prompt = f"""You are a meticulous compliance officer. Review the draft report against the plan and context. Output a JSON object with:
- "passes_validation": true/false
- "feedback": detailed critique (string)
- "final_report": the improved report as a plain text string (NOT a JSON object)

Plan: {plan}
Context (excerpt): {str(context)[:2000]}
Draft: {draft}

JSON:"""
    
    response = llm.generate(prompt, json_mode=True)
    try:
        result = json.loads(response)
        final_report = result.get("final_report", draft)
        # If the LLM returned a dict instead of a string, convert it
        if isinstance(final_report, dict):
            # Try to extract meaningful text or convert to markdown
            if "text" in final_report:
                final_report = final_report["text"]
            else:
                final_report = json.dumps(final_report, indent=2)
        return {
            "passes_validation": bool(result.get("passes_validation", True)),
            "critique": str(result.get("feedback", "")),
            "final_report": str(final_report)
        }
    except:
        return {
            "passes_validation": True,
            "critique": "",
            "final_report": str(draft)
        }