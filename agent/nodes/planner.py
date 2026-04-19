import json
import re
from core.llm_client import LLMClient

llm = LLMClient()

def planner_node(state: dict) -> dict:
    document_text = state.get("document_text", "")
    
    detection_prompt = f"""Analyze the first 1000 characters of this document and classify it into ONE of these categories:
- "resume" (CV, curriculum vitae, job application)
- "contract" (legal agreement, terms of service)
- "policy" (company policy, compliance document)
- "report" (research, analysis, article)
- "other"

Document excerpt:
{document_text[:1000]}

Return ONLY a JSON object with a single key "document_type". Example: {{"document_type": "resume"}}"""
    
    doc_type = "other"
    try:
        response = llm.generate(detection_prompt, json_mode=True)
        # If response indicates rate limit, use default
        if response.startswith("⚠️"):
            return {"plan": ["Summarize document", "Identify key points", "Provide recommendations"], "document_type": doc_type}
        result = json.loads(response)
        doc_type = result.get("document_type", "other")
    except:
        pass
    
    if doc_type == "resume":
        plan_prompt = f"""You are a career coach reviewing a resume. Break down the task of analyzing this resume into 3-5 specific subtasks. Output ONLY a valid JSON array of strings.

Resume excerpt:
{document_text[:2000]}

JSON array:"""
    elif doc_type == "contract":
        plan_prompt = f"""You are a compliance expert. Break down the task of auditing this contract into a list of 3-5 specific subtasks. Output ONLY a valid JSON array of strings.

Contract excerpt:
{document_text[:2000]}

JSON array:"""
    else:
        plan_prompt = f"""You are a document analyst. Break down the task of reviewing this document into a list of 3-5 specific subtasks. Output ONLY a valid JSON array of strings.

Document excerpt:
{document_text[:2000]}

JSON array:"""
    
    response = llm.generate(plan_prompt, json_mode=True)
    if response.startswith("⚠️"):
        return {"plan": ["Summarize document", "Identify key points", "Provide recommendations"], "document_type": doc_type}
    
    try:
        plan = json.loads(response)
        if isinstance(plan, list):
            return {"plan": plan, "document_type": doc_type}
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                plan = json.loads(match.group())
                return {"plan": plan, "document_type": doc_type}
            except:
                pass
    
    fallback = ["Summarize document", "Identify key points", "Provide recommendations"]
    return {"plan": fallback, "document_type": doc_type}