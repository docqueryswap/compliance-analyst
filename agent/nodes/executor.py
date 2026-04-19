from core.llm_client import LLMClient

llm = LLMClient()

def executor_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    doc_type = state.get("document_type", "other")
    
    context_str = "\n\n".join(context[:10]) if context else "No additional context available."
    
    if doc_type == "resume":
        prompt = f"""You are a professional career coach. Based on the resume content and any additional context, draft a concise resume analysis. Address each subtask in the plan.

Plan: {plan}

Resume Content & Context:
{context_str}

Structure your response as plain text with the following sections (use markdown-style headings):
## Executive Summary
(2-3 sentences)

## Strengths & Achievements
- Bullet point 1
- Bullet point 2

## Areas for Improvement
- Bullet point 1
- Bullet point 2

## Actionable Recommendations
- Bullet point 1
- Bullet point 2

Important:
- Output ONLY plain text, NOT JSON.
- Do NOT wrap your response in braces or quotes.
- Do NOT mention specific frameworks or external authors.

Draft Analysis:"""
    elif doc_type == "contract":
        prompt = f"""You are a compliance analyst. Based on the contract content and additional context, draft a concise compliance audit report. Address each subtask in the plan.

Plan: {plan}

Contract Content & Context:
{context_str}

Structure your response as plain text with these sections:
## Executive Summary
(2-3 sentences)

## Key Findings
- Bullet points

## Recommendations
- Bullet points

Output ONLY plain text, NOT JSON. Do NOT use braces or quotes.

Draft Report:"""
    elif doc_type == "policy":
        prompt = f"""You are a policy analyst. Based on the policy document and additional context, draft a concise policy review report. Address each subtask in the plan.

Plan: {plan}

Policy Content & Context:
{context_str}

Structure as plain text with:
## Executive Summary
## Key Findings
## Recommendations

Output ONLY plain text, NOT JSON.

Draft Report:"""
    else:
        prompt = f"""You are a document analyst. Based on the document and additional context, draft a concise analysis. Address each subtask in the plan.

Plan: {plan}

Document Content & Context:
{context_str}

Structure as plain text with:
## Executive Summary
## Key Insights
## Recommendations

Output ONLY plain text, NOT JSON.

Draft Analysis:"""
    
    draft = llm.generate(prompt)
    # Ensure it's a string
    return {"draft_report": str(draft)}