import os
import uuid
import logging
import json
import asyncio
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Langfuse import with fallback
try:
    from langfuse.decorators import observe
    LANGFUSE_OBSERVE_AVAILABLE = True
except ImportError:
    LANGFUSE_OBSERVE_AVAILABLE = False
    def observe(func=None, **kwargs):
        if func is not None:
            return func
        return lambda f: f

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom modules
from agent.graph import build_compliance_graph
from core.state_manager import StateManager
from core.vector_store import PineconeVectorStore
from core.llm_client import LLMClient
from sentence_transformers import SentenceTransformer
from document_processor import DocumentProcessor
from text_processor import TextProcessor

# Langfuse client (optional)
try:
    from core.langfuse_client import get_langfuse_handler, get_langfuse_client
    LANGFUSE_ENABLED = True
except ImportError:
    LANGFUSE_ENABLED = False
    logger.warning("Langfuse client not available. Tracing disabled.")

# ============================================================
# Helper: Format any report/critique object into readable text
# ============================================================
def format_report(report):
    """Convert dict or other types to a clean string."""
    if isinstance(report, dict):
        # If it has a 'text' field, use that directly
        if "text" in report:
            return str(report["text"])
        # Otherwise convert dict to readable markdown-style text
        parts = []
        for k, v in report.items():
            if isinstance(v, dict) and "text" in v:
                parts.append(f"**{k}**\n{v['text']}")
            else:
                parts.append(f"**{k}**\n{v}")
        return "\n\n".join(parts)
    return str(report) if report else ""

# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(title="Compliance Analyst", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Globals
compliance_graph = None
state_manager = StateManager()
vector_db = PineconeVectorStore()
embedder = SentenceTransformer("intfloat/multilingual-e5-large")
doc_proc = DocumentProcessor()
text_proc = TextProcessor()
llm = LLMClient()

@app.on_event("startup")
async def startup():
    global compliance_graph
    compliance_graph = build_compliance_graph()
    logger.info("✅ Compliance agent ready")

@app.get("/")
async def home():
    return FileResponse("templates/index.html")

class UploadResponse(BaseModel):
    client_id: str
    doc_id: str
    message: str

@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document."""
    client_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    
    content = await file.read()
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(content)
    
    text = doc_proc.process_uploaded_file(file_path)
    chunks = text_proc.split_text(text)
    embeddings = embedder.encode(chunks)
    
    vector_db.upsert_document(doc_id, chunks, embeddings)
    
    state_manager.save_state(client_id, {
        "document_text": text,
        "doc_id": doc_id,
        "filename": file.filename
    })
    
    return UploadResponse(
        client_id=client_id,
        doc_id=doc_id,
        message=f"✅ {file.filename} processed"
    )

class AuditRequest(BaseModel):
    client_id: str

@app.post("/audit")
async def run_audit(request: AuditRequest):
    """Run the full compliance audit workflow."""
    state = state_manager.get_state(request.client_id)
    if not state:
        return JSONResponse({"error": "Session not found"}, 404)
    
    initial_state = {
        "document_text": state["document_text"],
        "doc_id": state["doc_id"]
    }
    
    config = {}
    langfuse_handler = None
    if LANGFUSE_ENABLED:
        try:
            langfuse_handler = get_langfuse_handler()
            config = {"callbacks": [langfuse_handler]}
        except Exception as e:
            logger.warning(f"Langfuse handler failed: {e}")
    
    result = compliance_graph.invoke(initial_state, config=config)
    
    # Format outputs safely
    final_report = format_report(result.get("final_report", ""))
    critique = format_report(result.get("critique", ""))
    
    if langfuse_handler and LANGFUSE_ENABLED:
        try:
            langfuse = get_langfuse_client()
            trace_id = langfuse_handler.get_trace_id()
            langfuse.score(
                trace_id=trace_id,
                name="validation_passed",
                value=1.0 if result.get("passes_validation", True) else 0.0
            )
        except Exception as e:
            logger.warning(f"Could not record Langfuse score: {e}")
    
    return JSONResponse({
        "plan": result.get("plan", []),
        "draft": result.get("draft_report", ""),
        "critique": critique,
        "final_report": final_report,
        "passes_validation": result.get("passes_validation", True)
    })

@app.get("/audit/stream")
async def audit_stream(request: Request, client_id: str):
    """Stream the audit process using SSE."""
    state = state_manager.get_state(client_id)
    if not state:
        return JSONResponse({"error": "Session not found"}, 404)
    
    async def event_generator():
        yield {"event": "status", "data": "Planning audit..."}
        await asyncio.sleep(0.5)
        yield {"event": "status", "data": "Retrieving context..."}
        await asyncio.sleep(0.5)
        yield {"event": "status", "data": "Drafting report..."}
        await asyncio.sleep(0.5)
        yield {"event": "status", "data": "Reviewing with critic agent..."}
        
        initial_state = {"document_text": state["document_text"], "doc_id": state["doc_id"]}
        config = {}
        if LANGFUSE_ENABLED:
            try:
                config = {"callbacks": [get_langfuse_handler()]}
            except:
                pass
        
        result = compliance_graph.invoke(initial_state, config=config)
        final_report = format_report(result.get("final_report", ""))
        
        yield {
            "event": "result",
            "data": json.dumps({
                "final_report": final_report,
                "passes_validation": result.get("passes_validation", True)
            })
        }
    
    return EventSourceResponse(event_generator())