from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.embeddings import get_embedder


class TextProcessor:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
<<<<<<< HEAD
            chunk_size=900,
            chunk_overlap=180,
            separators=[
                "\n\nSection ",
                "\n\nSECTION ",
                "\n\nArticle ",
                "\n\nARTICLE ",
                "\n\nClause ",
                "\n\nCLAUSE ",
                "\n\n",
                "\n",
                ". ",
                "; ",
                " ",
            ],
=======
            chunk_size=500,
            chunk_overlap=50
>>>>>>> 26d5f9a99b0040c8382e1f5d679ffe2f90fd6bab
        )
        self.embedder = get_embedder()

    def split_text(self, text: str):
<<<<<<< HEAD
        normalized = "\n".join(line.strip() for line in text.splitlines())
        chunks = self.splitter.split_text(normalized)
        return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]

    def generate_embeddings(self, chunks):
        return self.embedder.encode(chunks)
=======
        return self.splitter.split_text(text)

    def generate_embeddings(self, chunks):
        return self.embedder.encode(chunks)
>>>>>>> 26d5f9a99b0040c8382e1f5d679ffe2f90fd6bab
