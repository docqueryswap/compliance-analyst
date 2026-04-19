import os
import time
import logging
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

class PineconeVectorStore:
    def __init__(self, index_name="multiagent"):   # <-- CHANGE TO EXISTING INDEX
        self.index_name = index_name
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not set")
        self.pc = Pinecone(api_key=api_key)
        
        # Check if index exists, but DO NOT create a new one
        existing = self.pc.list_indexes().names()
        if self.index_name not in existing:
            raise RuntimeError(f"Index '{self.index_name}' not found. Use an existing index or create one manually.")
        
        self.index = self.pc.Index(self.index_name)
        logger.info(f"✅ Connected to Pinecone index: {self.index_name}")
    
    def upsert_document(self, doc_id: str, chunks: list, embeddings: list):
        records = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            records.append({
                "id": f"{doc_id}-{i}",
                "values": emb.tolist(),
                "metadata": {"text": chunk, "doc_id": doc_id}
            })
        self.index.upsert(vectors=records)
    
    def search(self, query_embedding, top_k=5, doc_id=None):
        filter_dict = {"doc_id": {"$eq": doc_id}} if doc_id else None
        result = self.index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict
        )
        return [match["metadata"]["text"] for match in result["matches"]]
    
    def delete_by_metadata(self, metadata_filter):
        try:
            self.index.delete(filter=metadata_filter)
            logger.info(f"Deleted vectors with filter: {metadata_filter}")
        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")