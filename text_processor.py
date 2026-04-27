from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.embeddings import get_embedder


class TextProcessor:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        self.embedder = get_embedder()

    def split_text(self, text: str):
        return self.splitter.split_text(text)

    def generate_embeddings(self, chunks):
        return self.embedder.encode(chunks)