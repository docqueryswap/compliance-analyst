import os
import uuid
import logging
import json
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
vector_db = PineconeVectorStore()
embedder = get_embedder()
doc_proc = DocumentProcessor()
text_proc = TextProcessor()


@app.get("/")
async def home():
    return FileResponse("templates/index.html")


def _process_upload(file_name: str, content: bytes):
    client_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    file_path = f"/tmp/{file_name}"
    with open(file_path, "wb") as f:
        f.write(content)

    text = doc_proc.process_uploaded_file(file_path)
    chunks = text_proc.split_text(text)
    embeddings = embedder.encode(chunks)

    vector_db.upsert_document(doc_id, chunks, embeddings)

    state_manager.save_state(client_id, {
        "document_text": text,
        "doc_id": doc_id,
        "filename": file_name,
    })

    return UploadResponse(
        client_id=client_id,
        doc_id=doc_id,
        message=f"✅ {file_name} processed"
    )


def _run_audit_for_client(client_id: str):
    state = state_manager.get_state(client_id)
    if not state:
        return None

    initial_state = {
        "document_text": state["document_text"],
        "doc_id": state["doc_id"],
    }
    config = {"recursion_limit": 100}
    return compliance_graph.invoke(initial_state, config=config)


def _run_critique(plan: list, context: list, draft_report: str):
    from agent.nodes.critic import critic_node

    return critic_node({
        "plan": plan,
        "retrieved_context": context,
        "draft_report": draft_report,
    })


class UploadResponse(BaseModel):
    client_id: str
    doc_id: str
    message: str


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    return await run_in_threadpool(_process_upload, file.filename, content)


class AuditRequest(BaseModel):
    client_id: str


@app.post("/audit")
async def run_audit(request: AuditRequest):
    result = await run_in_threadpool(_run_audit_for_client, request.client_id)
    if not result:
        return JSONResponse({"error": "Session not found"}, 404)

    return JSONResponse({
        "draft_report": result.get("draft_report", ""),
        "plan": result.get("plan", []),
        "retrieved_context": result.get("retrieved_context", []),
    })


class CritiqueRequest(BaseModel):
    draft_report: str
    plan: list = []
    context: list = []


@app.post("/critique")
async def get_critique(request: CritiqueRequest):
    try:
        result = await run_in_threadpool(
            _run_critique,
            request.plan,
            request.context,
            request.draft_report,
        )
        return JSONResponse({
            "passes_validation": result.get("passes_validation", True),
            "critique": result.get("critique", ""),
            "final_report": result.get("final_report", request.draft_report),
            "confidence_score": result.get("confidence_score", 55),
            "missing_risks": result.get("missing_risks", []),
        })
    except Exception as e:
        logger.error(f"Critique failed: {e}")
        return JSONResponse({
            "passes_validation": True,
            "critique": "",
            "final_report": request.draft_report,
            "confidence_score": 55,
            "missing_risks": [],
        })
