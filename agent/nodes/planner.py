import json
from core.llm_client import LLMClient

llm = LLMClient()


DEFAULT_PLAN = [
    "Summarize document",
    "Identify key points",
    "Provide recommendations",
]


def planner_node(state: dict) -> dict:
    document_text = state.get("document_text", "")

    prompt = f"""Analyze the document excerpt and return a JSON object with:
- "document_type": exactly one of "resume", "contract", "policy", "report", "other"
- "plan": an array of 3-5 concise analysis subtasks tailored to the document

Return ONLY valid JSON in this shape:
{{"document_type": "contract", "plan": ["task 1", "task 2", "task 3"]}}

Document classification options:
- "resume"
- "contract"
- "policy"
- "report"
- "other"

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
                    plan = filtered_plan[:5]
        if doc_type not in {"resume", "contract", "policy", "report", "other"}:
            doc_type = "other"
    except:
        doc_type = "other"
        plan = DEFAULT_PLAN

    return {"plan": plan, "document_type": doc_type}
