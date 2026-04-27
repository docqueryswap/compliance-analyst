from core.vector_store import PineconeVectorStore
from core.web_search import WebSearchClient
from core.embeddings import get_embedder
import re

vector_db = PineconeVectorStore()
web_search = WebSearchClient()
embedder = get_embedder()

COMPLIANCE_TERMS = {
    "termination", "salary", "wage", "liability", "indemnity", "penalty",
    "non-compete", "non solicitation", "confidentiality", "privacy", "benefits",
    "leave", "notice", "dispute", "arbitration", "governing law", "severance",
    "misconduct", "intellectual property", "overtime", "compliance", "violation",
    "regulatory", "employment", "labor", "worker", "contract", "breach",
}


def _normalize_plan(plan: list) -> list:
    normalized = []
    seen = set()
    for item in plan:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _dedupe_context(items: list) -> list:
    deduped = []
    seen = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_candidate(query: str, candidate: str) -> float:
    query_tokens = _tokenize(query)
    candidate_tokens = _tokenize(candidate)
    if not candidate_tokens:
        return 0.0

    overlap = len(query_tokens & candidate_tokens)
    coverage = overlap / max(len(query_tokens), 1)
    compliance_hits = sum(1 for term in COMPLIANCE_TERMS if term in candidate.lower())
    length_bonus = 0.15 if 120 <= len(candidate) <= 1400 else 0.0
    clause_bonus = 0.2 if any(marker in candidate.lower() for marker in ("section", "clause", "termination", "liability")) else 0.0
    return coverage + (0.08 * compliance_hits) + length_bonus + clause_bonus


def _rerank_context(plan: list, candidates: list, limit: int = 8) -> list:
    scored = []
    for candidate in _dedupe_context(candidates):
        best_score = max((_score_candidate(task, candidate) for task in plan), default=0.0)
        if best_score >= 0.18:
            scored.append((best_score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in scored[:limit]]


def _build_web_query(task: str, doc_type: str) -> str:
    return f"{task} {doc_type} employment law compliance clause risk"


def retriever_node(state: dict) -> dict:
    plan = _normalize_plan(state.get("plan", []))
    doc_id = state.get("doc_id")
    doc_type = state.get("document_type", "other")
    context = []

    if not plan:
        return {"retrieved_context": []}

    embeddings = embedder.encode(plan)

    for subtask, emb in zip(plan, embeddings):
        docs = vector_db.search_similar(emb, top_k=5, doc_id=doc_id)
        context.extend(docs)

    ranked_context = _rerank_context(plan, context, limit=8)

    # Fall back to targeted web search only when local context is too thin.
    if len(ranked_context) < 4:
        web_context = []
        for subtask in plan[:2]:
            web_results = web_search.search(_build_web_query(subtask, doc_type), max_results=1)
            web_context.extend(web_results)
        ranked_context = _rerank_context(plan, ranked_context + web_context, limit=8)

    return {"retrieved_context": ranked_context}
