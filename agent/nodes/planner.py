import json
from core.llm_client import LLMClient

llm = LLMClient()

def planner_node(state: dict) -> dict:
    document_text = state.get("document_text", "")
    
    # First, detect document type
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
        result = json.loads(response)
        doc_type = result.get("document_type", "other")
    except:
        pass
    
    # Generate plan based on document type
    if doc_type == "resume":
        plan_prompt = f"""You are a career coach reviewing a resume. Break down the task of analyzing this resume into 3-5 specific subtasks. Output ONLY a JSON array of strings. Example: ["Extract key skills", "Check for quantifiable achievements", "Assess formatting and readability"]

Resume excerpt:
{document_text[:2000]}

JSON array:"""
    elif doc_type == "contract":
        plan_prompt = f"""You are a compliance expert. Break down the task of auditing this contract into a list of 3-5 specific subtasks. Output ONLY a JSON array of strings. Example: ["Identify key obligations", "Check for missing clauses", "Assess overall risk"]

Contract excerpt:
{document_text[:2000]}

JSON array:"""
    elif doc_type == "policy":
        plan_prompt = f"""You are a policy analyst. Break down the task of reviewing this policy document into a list of 3-5 specific subtasks. Output ONLY a JSON array of strings. Example: ["Identify compliance requirements", "Check for gaps in coverage", "Assess clarity and enforceability"]

Policy excerpt:
{document_text[:2000]}

JSON array:"""
    else:
        plan_prompt = f"""You are a document analyst. Break down the task of reviewing this document into a list of 3-5 specific subtasks. Output ONLY a JSON array of strings. Example: ["Summarize main points", "Identify key entities", "Extract actionable insights"]

Document excerpt:
{document_text[:2000]}

JSON array:"""
    
    response = llm.generate(plan_prompt, json_mode=True)
    try:
        plan = json.loads(response)
        if isinstance(plan, list):
            return {"plan": plan, "document_type": doc_type}
    except:
        pass
    
    # Fallback plans by document type
    if doc_type == "resume":
        fallback = ["Extract skills and experience", "Identify achievements", "Evaluate formatting", "Suggest improvements"]
    elif doc_type == "contract":
        fallback = ["Identify key obligations", "Check for missing clauses", "Assess overall risk"]
    elif doc_type == "policy":
        fallback = ["Identify compliance requirements", "Check for gaps", "Assess clarity"]
    else:
        fallback = ["Summarize document", "Extract key points", "Identify recommendations"]
    
    return {"plan": fallback, "document_type": doc_type}