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