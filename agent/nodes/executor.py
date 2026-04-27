from core.llm_client import LLMClient

llm = LLMClient()


def executor_node(state: dict) -> dict:
    plan = state.get("plan", [])
    context = state.get("retrieved_context", [])
    doc_type = state.get("document_type", "other")

    context_str = "\n\n".join(context[:10]) if context else "No additional context."

    prompt = f"""You are an expert analyst. Based on the document and context, draft a concise report addressing each subtask in the plan.

Plan: {plan}
Document type: {doc_type}
Context: {context_str}

Structure your report with:
## Executive Summary
## Key Findings
## Recommendations

Draft Report:"""

    draft = llm.generate(prompt, max_tokens=1500)
    return {"draft_report": draft}