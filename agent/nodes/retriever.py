from core.vector_store import PineconeVectorStore
from core.web_search import WebSearchClient
from sentence_transformers import SentenceTransformer

vector_db = PineconeVectorStore()
web_search = WebSearchClient()
embedder = SentenceTransformer("intfloat/multilingual-e5-large")


def retriever_node(state: dict) -> dict:
    plan = state.get("plan", [])
    doc_id = state.get("doc_id")
    context = []

    for subtask in plan:
        emb = embedder.encode(subtask)
        docs = vector_db.search_similar(emb, top_k=3, doc_id=doc_id)
        context.extend([doc["text"] for doc in docs])
        web_results = web_search.search(subtask, max_results=2)
        context.extend(web_results)

    return {"retrieved_context": context}