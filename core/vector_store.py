import os
import time
import logging
import base64
import unicodedata
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)


class PineconeVectorStore:
    def __init__(self, index_name: str = "multiagent-384"):
        self.index_name = index_name
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable not set")
        self.pc = Pinecone(api_key=api_key)
        self._ensure_index()
        self.index = self.pc.Index(self.index_name)
        logger.info(f"✅ Connected to Pinecone index: {self.index_name}")

    def _ensure_index(self):
        existing = self.pc.list_indexes().names()
        if self.index_name not in existing:
            logger.info(f"Index '{self.index_name}' not found. Creating...")
            self.pc.create_index(
                name=self.index_name,
                dimension=384,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
            while not self.pc.describe_index(self.index_name).status.get("ready", False):
                time.sleep(2)
            logger.info(f"Index '{self.index_name}' created.")

    def _encode_metadata_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFC", text or "")
        return base64.b64encode(normalized.encode("utf-8")).decode("ascii")

    def _decode_metadata_text(self, metadata: dict) -> str:
        encoded_text = metadata.get("text_b64")
        if encoded_text:
            return base64.b64decode(encoded_text).decode("utf-8")
        return metadata.get("text", "")

    def upsert_document(self, doc_id: str, chunks: list, embeddings: list):
        records = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            records.append({
                "id": f"{doc_id}-{i}",
                "values": emb.tolist(),
                "metadata": {
                    "text_b64": self._encode_metadata_text(chunk),
                    "doc_id": doc_id,
                }
            })
        self.index.upsert(vectors=records)

    def search_similar(self, query_embedding, top_k: int = 5, doc_id: str = None):
        filter_dict = {"doc_id": {"$eq": doc_id}} if doc_id else None
        result = self.index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict
        )
        return [self._decode_metadata_text(match["metadata"]) for match in result["matches"]]
