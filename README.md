---
title: Compliance Analyst
emoji: 📋
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Autonomous Compliance Analyst

Upload a contract or policy document. AI agents will audit it and generate a compliance report.

## Features
- Multi‑agent workflow (Planner → Retriever → Executor → Critic)
- RAG with Pinecone vector search
- Live web research via Tavily
- Full observability with Langfuse
- Multi‑user state with Redis

## Tech Stack
- FastAPI + LangGraph
- Groq (Llama 3.1)
- Pinecone + Tavily
- Langfuse + RAGAS
- Docker + Hugging Face Spaces

- # 🧠 Autonomous Compliance Analyst

A production-grade **multi-agent AI system** that autonomously audits documents against live regulations and internal knowledge using agentic workflows, RAG, and real-time evaluation.

---

## 🚀 Live Demo

* Hugging Face Spaces (Primary)
* AWS EC2 Deployment (Cloud Proof)

---

## 🧩 What It Does

Upload a document (contract, resume, policy) → get:

* 📄 Executive summary
* ⚖️ Compliance analysis
* 🔍 External validation (web search)
* 📊 Structured report with scores

---

## 🏗️ System Architecture

```
User Upload
   ↓
FastAPI Backend
   ↓
LangGraph Agent Flow
   ├── Planner → Task decomposition
   ├── Retriever → Pinecone (RAG) + Tavily (Web)
   ├── Executor → Report generation
   └── Critic → Validation (LLM-as-judge)
   ↓
Final Structured Report
```

---

## ⚙️ Key Features

* 🧠 Multi-agent orchestration (Planner → Retriever → Executor → Critic)
* 🔍 Retrieval-Augmented Generation (RAG)
* 🌐 Live web validation (Tavily)
* 📊 LLM observability (Langfuse)
* 👥 Multi-user state (Redis)
* ☁️ Cloud deployment (AWS EC2)
* 🔁 CI/CD pipeline (GitHub Actions)
* 🔌 MCP server (AI agent tool integration)

---

## 🧠 Engineering Highlights

### 🔹 From Prototype → Production

Started as a basic RAG app → evolved into **autonomous agent system**

---

### 🔹 Major Challenges Solved

* ❌ SSE/WebSocket streaming failure → ✅ switched to polling architecture
* ❌ File-based state inconsistency → ✅ Redis-based distributed state
* ❌ OOM crashes on EC2 → ✅ swap memory + model optimization
* ❌ Vector dimension mismatch → ✅ aligned embedding + index config
* ❌ Hidden config bugs → ✅ full codebase grep debugging

---

### 🔹 Observability & Optimization

* Tracked token usage and latency using Langfuse
* Reduced response latency by optimizing agent prompts
* Added validation scoring for output reliability

---

## 📊 Tech Stack

* **Backend:** FastAPI, Uvicorn
* **Agents:** LangGraph
* **LLM:** Groq (Llama 3.1)
* **Embeddings:** sentence-transformers (384-dim)
* **Vector DB:** Pinecone
* **State:** Redis
* **Search:** Tavily
* **Monitoring:** Langfuse
* **Deployment:** AWS EC2 + Hugging Face Spaces
* **CI/CD:** GitHub Actions

---

## 🧪 API Flow

```
POST /upload
POST /correlate/start
GET  /correlate/status/{job_id}
```

---

## 🧭 Key Learnings

* Infrastructure limitations can break ideal architectures
* Distributed systems require external state (Redis > files)
* Observability is essential for debugging AI systems
* Practical tradeoffs > theoretical perfection

---

## 💡 Future Improvements

* Real-time streaming via WebSocket gateway
* Horizontal scaling with container orchestration
* Cost optimization via caching + batching

---

## 👤 Author

AI Engineer focused on **LLM systems, agentic workflows, and production AI infrastructure**

---
