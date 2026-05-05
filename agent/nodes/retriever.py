from core.vector_store import PineconeVectorStore
from core.web_search import WebSearchClient
from core.embeddings import get_embedder
import re

vector_db = PineconeVectorStore()
web_search = WebSearchClient()
embedder = get_embedder()


# Compliance terms now organized by domain to prevent cross-contamination
COMPLIANCE_TERMS_BY_TYPE = {
    "consumer_loan": {
        "usury", "interest rate", "apr", "annual percentage rate", "finance charge",
        "collateral", "security interest", "repossession", "ucc", "uniform commercial code",
        "truth in lending", "tila", "regulation z", "predatory lending", "prepayment penalty",
        "late fee", "acceleration clause", "default", "promissory note", "installment",
        "credit", "underwriting", "ability to repay", "cfpb", "consumer financial protection",
        "right of rescission", "cooling off", "disclosure", "plain text", "pii", "privacy",
        "social security", "ssn", "data protection", "gramm leach bliley",
    },
    "employment": {
        "termination", "salary", "wage", "liability", "indemnity", "penalty",
        "non-compete", "non solicitation", "confidentiality", "privacy", "benefits",
        "leave", "notice", "dispute", "arbitration", "governing law", "severance",
        "misconduct", "intellectual property", "overtime", "compliance", "violation",
        "regulatory", "employment", "labor", "worker", "contract", "breach",
        "flsa", "fair labor standards", "eeoc", "discrimination", "harassment",
        "retaliation", "fmla", "family medical leave", "worker classification",
        "independent contractor", "at-will", "wrongful termination",
    },
    "nda": {
        "confidential", "trade secret", "proprietary", "non-disclosure", "nda",
        "non-circumvent", "non-use", "return of materials", "injunctive relief",
        "survival period", "exclusions", "third party disclosure", "subpoena",
        "defend trade secrets act", "dtsa", "economic espionage",
    },
    "student_loan": {
        "student loan", "education loan", "tuition", "deferment", "forbearance",
        "income driven repayment", "public service loan forgiveness", "pslf",
        "higher education act", "direct loan", "perkins", "fafsa", "co-signer",
        "discharge", "cancellation", "borrower defense", "accreditation",
    },
    "lease": {
        "lease", "rental", "landlord", "tenant", "security deposit", "eviction",
        "habitability", "quiet enjoyment", "sublease", "assignment", "holdover",
        "notice to quit", "cure period", "late rent", "utilities", "maintenance",
        "repair", "entry right", "inspection", "renewal", "rent control",
    },
    "service_agreement": {
        "service level", "sla", "statement of work", "deliverable", "milestone",
        "acceptance", "warranty", "indemnification", "limitation of liability",
        "force majeure", "termination for convenience", "termination for cause",
        "intellectual property", "work for hire", "license", "royalty",
        "non-solicitation", "data processing", "gdpr", "data security",
    },
    "other": {
        "breach", "remedy", "damages", "liquidated damages", "specific performance",
        "force majeure", "severability", "entire agreement", "modification",
        "waiver", "assignment", "successors", "counterparts", "governing law",
        "jurisdiction", "venue", "arbitration", "mediation", "dispute resolution",
        "termination", "notice", "confidentiality", "indemnity", "liability",
        "insurance", "warranty", "representation", "covenant",
    },
}


def _normalize_plan(plan: list) -> list:
    normalized = []
    seen = set()
    for item in plan:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _dedupe_context(items: list) -> list:
    deduped = []
    seen = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_candidate(query: str, candidate: str, doc_type: str) -> float:
    query_tokens = _tokenize(query)
    candidate_tokens = _tokenize(candidate)
    if not candidate_tokens:
        return 0.0

    overlap = len(query_tokens & candidate_tokens)
    coverage = overlap / max(len(query_tokens), 1)
    
    # Score based on domain-relevant terms ONLY
    domain_terms = COMPLIANCE_TERMS_BY_TYPE.get(doc_type, COMPLIANCE_TERMS_BY_TYPE["other"])
    compliance_hits = sum(
        1 for term in domain_terms 
        if term.lower() in candidate.lower()
    )
    
    length_bonus = 0.15 if 120 <= len(candidate) <= 1400 else 0.0
    clause_bonus = 0.2 if any(
        marker in candidate.lower() 
        for marker in ("section", "clause", "§", "article", "provision")
    ) else 0.0
    
    return coverage + (0.08 * compliance_hits) + length_bonus + clause_bonus


def _rerank_context(plan: list, candidates: list, doc_type: str, limit: int = 8) -> list:
    scored = []
    for candidate in _dedupe_context(candidates):
        best_score = max(
            (_score_candidate(task, candidate, doc_type) for task in plan),
            default=0.0
        )
        if best_score >= 0.18:
            scored.append((best_score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in scored[:limit]]


def _build_web_query(task: str, doc_type: str) -> str:
    """Build a domain-specific web search query. No hardcoded 'employment'."""
    domain_terms_map = {
        "consumer_loan": "consumer lending law usury ucc repossession",
        "employment": "employment labor law flsa termination",
        "nda": "confidentiality trade secret nda enforceability",
        "student_loan": "student loan higher education act tila",
        "lease": "landlord tenant law lease eviction security deposit",
        "service_agreement": "service agreement sla limitation liability",
        "other": "contract law enforceability breach remedy",
    }
    domain_context = domain_terms_map.get(doc_type, domain_terms_map["other"])
    return f"{task} {domain_context} compliance legal requirements"


def retriever_node(state: dict) -> dict:
    plan = _normalize_plan(state.get("plan", []))
    doc_id = state.get("doc_id")
    doc_type = state.get("document_type", "other")
    context = []

    if not plan:
        return {"retrieved_context": []}

    # Embed each plan item and search vector DB
    embeddings = embedder.encode(plan)

    for subtask, emb in zip(plan, embeddings):
        docs = vector_db.search_similar(emb, top_k=5, doc_id=doc_id)
        context.extend(docs)

    # Rerank using domain-specific terms
    ranked_context = _rerank_context(plan, context, doc_type, limit=8)

    # Fall back to targeted web search when local context is too thin
    if len(ranked_context) < 4:
        web_context = []
        for subtask in plan[:2]:
            web_results = web_search.search(
                _build_web_query(subtask, doc_type),
                max_results=1
            )
            web_context.extend(web_results)
        ranked_context = _rerank_context(plan, ranked_context + web_context, doc_type, limit=8)

    return {"retrieved_context": ranked_context}