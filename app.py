import os
import uuid
import logging
import json
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from agent.graph import build_compliance_graph
from core.state_manager import StateManager
from core.vector_store import PineconeVectorStore
from core.embeddings import get_embedder
from document_processor import DocumentProcessor
from text_processor import TextProcessor

app = FastAPI(title="Compliance Analyst", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

compliance_graph = build_compliance_graph()
state_manager = StateManager()
doc_proc = DocumentProcessor()
vector_db = None
embedder = None
text_proc = None


def _get_vector_db():
    global vector_db
    if vector_db is None:
        vector_db = PineconeVectorStore()
    return vector_db


def _get_embedder():
    global embedder
    if embedder is None:
        embedder = get_embedder()
    return embedder


def _get_text_processor():
    global text_proc
    if text_proc is None:
        text_proc = TextProcessor()
    return text_proc


@app.get("/")
async def home():
    return FileResponse("templates/index.html")


def _process_upload(file_name: str, content: bytes):
    client_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    safe_file_name = Path(file_name or "uploaded_document.txt").name
    file_path = f"/tmp/{safe_file_name}"
    with open(file_path, "wb") as f:
        f.write(content)

    text = doc_proc.process_uploaded_file(file_path)
    chunks = _get_text_processor().split_text(text)
    vector_ready = False
    try:
        embeddings = _get_embedder().encode(chunks)
        _get_vector_db().upsert_document(doc_id, chunks, embeddings)
        vector_ready = True
    except Exception as e:
        logger.warning("Vector indexing unavailable; audit will use local document context: %s", e)

    state_manager.save_state(client_id, {
        "document_text": text,
        "document_chunks": chunks,
        "doc_id": doc_id,
        "filename": safe_file_name,
        "vector_ready": vector_ready,
    })

    return UploadResponse(
        client_id=client_id,
        doc_id=doc_id,
        message=f"✅ {safe_file_name} processed"
    )


def _run_audit_for_client(client_id: str):
    state = state_manager.get_state(client_id)
    if not state:
        return None

    initial_state = {
        "document_text": state["document_text"],
        "doc_id": state["doc_id"],
        "document_chunks": state.get("document_chunks", []),
    }
    config = {"recursion_limit": 100}
    return compliance_graph.invoke(initial_state, config=config)


def _run_critique(plan: list, context: list, draft_report: str, document_type: str = "other"):
    from agent.nodes.critic import critic_node

    return critic_node({
        "plan": plan,
        "retrieved_context": context,
        "draft_report": draft_report,
        "document_type": document_type,
    })


class UploadResponse(BaseModel):
    client_id: str
    doc_id: str
    message: str


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        return await run_in_threadpool(_process_upload, file.filename, content)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return JSONResponse({"error": "Upload failed. Please verify the file type and try again."}, 500)


class AuditRequest(BaseModel):
    client_id: str


@app.post("/audit")
async def run_audit(request: AuditRequest):
    try:
        result = await run_in_threadpool(_run_audit_for_client, request.client_id)
        if not result:
            return JSONResponse({"error": "Session not found"}, 404)
    except Exception as e:
        logger.error(f"Audit failed: {e}")
        return JSONResponse({"error": "Audit failed. Please try again or upload the document again."}, 500)

    return JSONResponse({
        "draft_report": result.get("draft_report", ""),
        "plan": result.get("plan", []),
        "retrieved_context": result.get("retrieved_context", []),
        "document_type": result.get("document_type", "other"),
    })


class CritiqueRequest(BaseModel):
    draft_report: str
    plan: list = []
    context: list = []
    document_type: str = "other"


@app.post("/critique")
async def get_critique(request: CritiqueRequest):
    try:
        result = await run_in_threadpool(
            _run_critique,
            request.plan,
            request.context,
            request.draft_report,
            request.document_type,
        )
        confidence_score = result.get("confidence_score", 55)
        try:
            confidence_score = int(confidence_score)
        except (TypeError, ValueError):
            confidence_score = 55

        return JSONResponse({
            "passes_validation": result.get("passes_validation", True),
            "critique": str(result.get("critique", "") or ""),
            "final_report": str(result.get("final_report", request.draft_report) or request.draft_report),
            "confidence_score": max(0, min(100, confidence_score)),
            "missing_risks": result.get("missing_risks", []) if isinstance(result.get("missing_risks", []), list) else [],
            "_fallback_triggered": bool(result.get("_fallback_triggered", False)),
        })
    except Exception as e:
        logger.error(f"Critique failed: {e}")
        return JSONResponse({
            "passes_validation": False,
            "critique": "Critique failed on the server. Report reflects initial draft only. Human review required.",
            "final_report": request.draft_report,
            "confidence_score": 55,
            "missing_risks": [],
            "_fallback_triggered": True,
        })
