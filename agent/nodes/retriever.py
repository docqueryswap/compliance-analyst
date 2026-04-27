from core.vector_store import PineconeVectorStore
from core.web_search import WebSearchClient
from core.embeddings import get_embedder

vector_db = PineconeVectorStore()
web_search = WebSearchClient()
embedder = get_embedder()


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


def retriever_node(state: dict) -> dict:
    plan = _normalize_plan(state.get("plan", []))
    doc_id = state.get("doc_id")
    context = []

    if not plan:
        return {"retrieved_context": []}

    embeddings = embedder.encode(plan)

    for subtask, emb in zip(plan, embeddings):
        docs = vector_db.search_similar(emb, top_k=3, doc_id=doc_id)
        context.extend(docs)

    context = _dedupe_context(context)

    # Fall back to web search only when document retrieval returns too little context.
    if len(context) < 3:
        for subtask in plan[:2]:
            web_results = web_search.search(subtask, max_results=2)
            context.extend(web_results)

    return {"retrieved_context": _dedupe_context(context)}
