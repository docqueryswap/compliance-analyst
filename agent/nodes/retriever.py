from core.vector_store import PineconeVectorStore
from core.web_search import WebSearchClient
from core.embeddings import get_embedder

vector_db = PineconeVectorStore()
web_search = WebSearchClient()
embedder = get_embedder()


def retriever_node(state: dict) -> dict:
    plan = state.get("plan", [])
    doc_id = state.get("doc_id")
    context = []

    for subtask in plan:
        emb = embedder.encode(subtask)
        docs = vector_db.search_similar(emb, top_k=3, doc_id=doc_id)
        context.extend(docs)
        web_results = web_search.search(subtask, max_results=2)
        context.extend(web_results)

    return {"retrieved_context": context}