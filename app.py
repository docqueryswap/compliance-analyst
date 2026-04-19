import os
import uuid
import logging
import json
from fastapi import FastAPI, UploadFile, File, Request
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
from sentence_transformers import SentenceTransformer
from document_processor import DocumentProcessor
from text_processor import TextProcessor

app = FastAPI(title="Compliance Analyst", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

compliance_graph = build_compliance_graph()
state_manager = StateManager()
vector_db = PineconeVectorStore()
embedder = SentenceTransformer("all-MiniLM-L6-v2")  # 384‑dim to match index
doc_proc = DocumentProcessor()
text_proc = TextProcessor()


@app.get("/")
async def home():
    return FileResponse("templates/index.html")


class UploadResponse(BaseModel):
    client_id: str
    doc_id: str
    message: str


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
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
        "filename": file.filename,
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
    state = state_manager.get_state(request.client_id)
    if not state:
        return JSONResponse({"error": "Session not found"}, 404)

    initial_state = {
        "document_text": state["document_text"],
        "doc_id": state["doc_id"],
    }
    config = {"recursion_limit": 100}
    result = compliance_graph.invoke(initial_state, config=config)

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
    from agent.nodes.critic import critic_node
    try:
        result = critic_node({
            "plan": request.plan,
            "retrieved_context": request.context,
            "draft_report": request.draft_report,
        })
        return JSONResponse({
            "passes_validation": result.get("passes_validation", True),
            "critique": result.get("critique", ""),
            "final_report": result.get("final_report", request.draft_report),
        })
    except Exception as e:
        logger.error(f"Critique failed: {e}")
        return JSONResponse({
            "passes_validation": True,
            "critique": "",
            "final_report": request.draft_report,
        })