import json
from core.llm_client import LLMClient

llm = LLMClient()


def planner_node(state: dict) -> dict:
    document_text = state.get("document_text", "")

    # Detect document type
    detection_prompt = f"""Analyze the first 1000 characters of this document and classify it into ONE category:
- "resume"
- "contract"
- "policy"
- "report"
- "other"

Return ONLY a JSON object: {{"document_type": "category"}}

Document:
{document_text[:1000]}"""

    doc_type = "other"
    try:
        response = llm.generate(detection_prompt, json_mode=True)
        result = json.loads(response)
        doc_type = result.get("document_type", "other")
    except:
        pass

    # Generate plan
    if doc_type == "resume":
        prompt = f"""Break this resume analysis into 3-5 subtasks. Return ONLY a JSON array of strings.
Resume: {document_text[:1500]}"""
    elif doc_type == "contract":
        prompt = f"""Break this contract audit into 3-5 subtasks. Return ONLY a JSON array of strings.
Contract: {document_text[:1500]}"""
    elif doc_type == "policy":
        prompt = f"""Break this policy review into 3-5 subtasks. Return ONLY a JSON array of strings.
Policy: {document_text[:1500]}"""
    else:
        prompt = f"""Break this document analysis into 3-5 subtasks. Return ONLY a JSON array of strings.
Document: {document_text[:1500]}"""

    plan = []
    try:
        response = llm.generate(prompt, json_mode=True)
        plan = json.loads(response)
        if not isinstance(plan, list):
            plan = ["Summarize document", "Identify key points", "Provide recommendations"]
    except:
        plan = ["Summarize document", "Identify key points", "Provide recommendations"]

    return {"plan": plan, "document_type": doc_type}