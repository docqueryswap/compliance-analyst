import os
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

_langfuse_client = None
_langfuse_handler = None

def get_langfuse_client():
    """Return a singleton Langfuse client."""
    global _langfuse_client
    if _langfuse_client is None:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        
        if not public_key or not secret_key:
            raise ValueError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
        
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
    return _langfuse_client

def get_langfuse_handler():
    """Return a singleton Langfuse CallbackHandler for LangChain/LangGraph."""
    global _langfuse_handler
    if _langfuse_handler is None:
        _langfuse_handler = CallbackHandler()
    return _langfuse_handler