"""
Document type classifier using rule-based pattern matching.
Fast, deterministic, and extensible.
Now includes an ensemble auditability score (zero API, zero cost).
"""
import re
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ContractType(str, Enum):
    CONSUMER_LOAN = "consumer_loan"
    STUDENT_LOAN = "student_loan"
    EMPLOYMENT = "employment"
    NDA = "nda"
    SERVICE_AGREEMENT = "service_agreement"
    LEASE = "lease"
    OTHER = "other"


# Sentinel for documents that are explicitly not contracts
NON_AUDITABLE = "__non_auditable__"


# Priority-ordered: most specific patterns first
CLASSIFICATION_RULES = [
    # (regex_pattern, contract_type, confidence_boost)

    # Employment indicators
    (r"employment\s+(agreement|contract)", ContractType.EMPLOYMENT, 0.6),
    (r"(employee\s+and\s+employer|employer\s+and\s+employee)", ContractType.EMPLOYMENT, 0.5),
    (r"working\s+hours|overtime\s+(pay|compensation)|annual\s+leave|sick\s+leave|termination\s+notice\s+period", ContractType.EMPLOYMENT, 0.3),
    (r"probation\s+period|notice\s+of\s+termination|severance\s+pay", ContractType.EMPLOYMENT, 0.3),

    # Student loan indicators
    (r"student\s+loan|education\s+loan|tuition\s+fee|academic\s+year", ContractType.STUDENT_LOAN, 0.6),
    (r"fafsa|direct\s+loan|perkins\s+loan|in[- ]school\s+deferment", ContractType.STUDENT_LOAN, 0.5),

    # Consumer loan indicators
    (r"(consumer\s+loan\s+agreement|loan\s+agreement|credit\s+agreement)", ContractType.CONSUMER_LOAN, 0.7),
    (r"(borrower\s*:.*\n.*lender\s*:|lender\s*:.*\n.*borrower\s*:)", ContractType.CONSUMER_LOAN, 0.5),
    (r"(borrower\s+and\s+lender|lender\s+and\s+borrower)", ContractType.CONSUMER_LOAN, 0.5),
    (r"interest\s+of\s+\d+\.?\d*\s*%\s*per\s+(month|annum|year)", ContractType.CONSUMER_LOAN, 0.4),
    (r"annual\s+percentage\s+rate|apr\s*[:%]|finance\s+charge", ContractType.CONSUMER_LOAN, 0.4),
    (r"(fiduciary\s+lien|execution\s+of\s+the\s+guarantee|security\s+interest|collateral|repossession|usury|promissory\s+note)", ContractType.CONSUMER_LOAN, 0.3),
    (r"financed?\s+(amount|asset)", ContractType.CONSUMER_LOAN, 0.3),
    (r"(the\s+asset\s+described\s+in|financed?\s+asset)", ContractType.CONSUMER_LOAN, 0.2),
    (r"(principal\s+amount|monthly\s+payment|installment|amortization)", ContractType.CONSUMER_LOAN, 0.2),
    (r"late\s+interest\s+of\s+\d+\.?\d*\s*%\s*per\s+month", ContractType.CONSUMER_LOAN, 0.2),

    # NDA indicators
    (r"non[- ]disclosure\s+agreement|confidentiality\s+agreement", ContractType.NDA, 0.6),
    (r"(confidential\s+information|trade\s+secret|proprietary\s+information|non[- ]circumvent)", ContractType.NDA, 0.4),

    # Service agreement indicators
    (r"(service\s+level\s+agreement|sla|statement\s+of\s+work|master\s+services?\s+agreement)", ContractType.SERVICE_AGREEMENT, 0.5),
    (r"vendor\s+agreement|independent\s+contractor", ContractType.SERVICE_AGREEMENT, 0.5),
    (r"scope\s+of\s+(engagement|work|services)", ContractType.SERVICE_AGREEMENT, 0.3),
    (r"net[- ]\d+\s+(basis|days|payment\s+terms)", ContractType.SERVICE_AGREEMENT, 0.2),
    (r"(deliverables|milestone|acceptance\s+criteria)", ContractType.SERVICE_AGREEMENT, 0.3),

    # Lease indicators
    (r"(lease\s+agreement|rental\s+agreement|tenancy\s+agreement)", ContractType.LEASE, 0.5),
    (r"(lessor\s+and\s+lessee|landlord\s+and\s+tenant)", ContractType.LEASE, 0.4),
    (r"(security\s+deposit|monthly\s+rent|premises|eviction)", ContractType.LEASE, 0.3),
]


# Negative patterns: documents that are definitely NOT contracts
NEGATIVE_PATTERNS = [
    (r"\bQ\d+\b", 0.5),                         # Q1, Q2 … (interview)
    (r"\bA\d+\b", 0.5),                         # A1, A2 …
    (r"(interview|prep|study\s+guide)", 0.7),   # educational
    (r"(this\s+is\s+not\s+(a\s+)?legal\s+advice)", 0.8),
    (r"(for\s+educational\s+purposes\s+only)", 0.8),
    (r"(template\s+(contract|agreement)|sample\s+(contract|agreement))", 0.6),
    (r"(role\s+in\s+AI|stack\s*:|section\s+\d+\s*:\s*architecture)", 0.4),  # tech ref / resume
    (r"##\s+(Technical\s+Skills|Professional\s+Summary)", 0.6),              # resume
    (r"import\s+\w+", 0.7),                     # code
]


# Structural anchors that strongly indicate a real contract
STRUCTURAL_ANCHORS = [
    r"\d+\.\s+[A-Z][A-Z\s]{3,}",          # Numbered section: "1. DEFINITIONS"
    r"(?:WHEREAS|WITNESSETH|NOW\s+TH\S+)", # Recitals
    r"signature\s*(?:block|page|lines?)",
    r"/s/|signed\s*(?:by|at)",
    r"IN\s+WITNESS\s+WHEREOF",
]


# Legal keywords to help split merged PDF text
LEGAL_KEYWORDS = [
    'agreement', 'contract', 'vendor', 'client', 'party', 'parties',
    'hereinafter', 'referred', 'entered', 'into', 'between',
    'effective', 'date', 'scope', 'engagement', 'work', 'services',
    'goods', 'payment', 'terms', 'net', 'basis', 'days',
    'representation', 'warranties', 'liability', 'termination',
    'notice', 'dispute', 'resolution', 'governing', 'law',
    'signature', 'signed', 'amendments', 'severability', 'delays',
    'notices', 'failure', 'maintain', 'coverage', 'independent',
    'contractor', 'employee', 'employer', 'employment',
    'confidential', 'information', 'non-disclosure', 'nda',
    'lease', 'rental', 'tenancy', 'lessor', 'lessee', 'landlord', 'tenant',
    'loan', 'borrower', 'lender', 'interest', 'finance', 'principal',
    'collateral', 'repossession', 'installment', 'amortization',
    'shall', 'must', 'will', 'hereby', 'hereto', 'whereas', 'thereof',
    'therein', 'forthwith', 'indemnify', 'warrant', 'represent', 'covenant',
    'aforesaid', 'pursuant', 'notwithstanding', 'herein', 'breach',
    'arbitration', 'jurisdiction', 'clause', 'obligation',
]


def _clean_pdf_text(text: str) -> str:
    """
    Fix malformed PDF text where spaces were stripped during extraction.
    Uses keyword-based splitting for uppercase concatenated text.
    """
    # Force lowercase for consistent matching
    text_lower = text.lower()

    # Split on known legal keywords when they're merged with adjacent text
    for kw in LEGAL_KEYWORDS:
        # Insert space BEFORE the keyword if it's merged with preceding text
        text_lower = re.sub(rf'(\w){re.escape(kw)}', rf'\1 {kw}', text_lower)
        # Insert space AFTER the keyword if it's merged with following text
        text_lower = re.sub(rf'{re.escape(kw)}(\w)', rf'{kw} \1', text_lower)

    # Also fix camelCase: "thisVendorAgreement" -> "this Vendor Agreement"
    text_lower = re.sub(r'([a-z])([A-Z])', r'\1 \2', text_lower)

    # Collapse multiple spaces
    text_lower = re.sub(r'\s+', ' ', text_lower)

    return text_lower


def _legalese_density(text: str) -> float:
    """Ratio of legalese terms to total words, scaled to 0-1."""
    legalese_terms = {
        "hereto", "hereinafter", "whereas", "thereof", "therein",
        "forthwith", "indemnify", "warrant", "represent", "covenant",
        "hereby", "aforesaid", "pursuant", "notwithstanding", "herein",
        "termination", "breach", "arbitration", "jurisdiction", "clause",
        "shall", "obligation", "dispute", "governing law",
        "agreement", "contract", "party", "parties"
    }
    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return 0.0
    count = sum(1 for w in words if w in legalese_terms)
    return min(count / len(words) * 10, 1.0)


def classify_document(text: str) -> ContractType:
    """
    Classify a document by scoring regex patterns.
    Returns the highest-scoring contract type, or NON_AUDITABLE if negative patterns match.
    """
    text_lower = _clean_pdf_text(text)

    # ── Hard rejection: negative patterns ──
    for neg_pattern, _ in NEGATIVE_PATTERNS:
        if re.search(neg_pattern, text_lower):
            logger.info(f"Hard rejected by negative pattern: {neg_pattern}")
            return NON_AUDITABLE

    # ── Positive scoring ──
    scores = {ct: 0.0 for ct in ContractType}
    for pattern, contract_type, boost in CLASSIFICATION_RULES:
        if re.search(pattern, text_lower):
            scores[contract_type] += boost

    best_type = max(scores, key=scores.get)
    if scores[best_type] < 0.5:
        return ContractType.OTHER
    return best_type


def compute_auditability_score(text: str) -> float:
    """
    Ensemble score (0-1): how likely the document is a real contract.
    Per‑type normalisation — a strong consumer loan isn't penalised for
    not being an employment contract.
    """
    # ── 0. Clean malformed PDF text (stripped spaces) ──
    text_lower = _clean_pdf_text(text)
    logger.info(f"CLEANED TEXT (first 300 chars): {text_lower[:300]}")

    # ── 1. Per‑type positive signal ──
    scores = {ct: 0.0 for ct in ContractType}
    for pattern, ct, boost in CLASSIFICATION_RULES:
        if re.search(pattern, text_lower):
            scores[ct] += boost

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # A concise contract will not contain every possible signal for its type.
    # Cap the normalizer so strong title/party/rate evidence is enough to pass.
    type_boosts = [b for _, ct, b in CLASSIFICATION_RULES if ct == best_type]
    max_type_score = sum(type_boosts) if type_boosts else 1.0
    target_type_score = min(max_type_score, 1.5)

    pos_score = min(best_score / target_type_score, 1.0) if target_type_score > 0 else 0.0

    # ── 2. Negative penalty ──
    neg_penalty = 0.0
    for neg_pat, weight in NEGATIVE_PATTERNS:
        if re.search(neg_pat, text_lower):
            neg_penalty += weight
            logger.debug(f"Negative match: {neg_pat} (-{weight})")
    neg_penalty = min(neg_penalty, 1.0)

    # ── 3. Structural bonus ──
    struct_bonus = 0.0
    for anchor in STRUCTURAL_ANCHORS:
        if re.search(anchor, text_lower, re.IGNORECASE):
            struct_bonus += 0.1
            logger.debug(f"Structural anchor match: {anchor} (+0.1)")
    struct_bonus = min(struct_bonus, 0.3)

    # ── 4. Lexical density ──
    density = _legalese_density(text_lower)

    # ── Debug: log all components ──
    logger.info(
        f"AUDITABILITY SCORE | best_type={best_type.value} | "
        f"pos_score={pos_score:.3f} | neg_penalty={neg_penalty:.3f} | "
        f"struct_bonus={struct_bonus:.3f} | density={density:.3f}"
    )

    # ── Weighted sum ──
    score = (
        pos_score * 0.5
        + (-neg_penalty) * 0.3
        + struct_bonus * 0.2
        + density * 0.2
    )
    final_score = max(0.0, min(score, 1.0))
    logger.info(f"FINAL SCORE: {final_score:.3f} | threshold=0.35 | passed={final_score >= 0.35}")

    return final_score


def get_party_labels(contract_type: ContractType) -> dict:
    """Returns expected party role labels for a contract type."""
    party_map = {
        ContractType.CONSUMER_LOAN: {"party_a": "Lender", "party_b": "Borrower", "relationship": "lending"},
        ContractType.STUDENT_LOAN: {"party_a": "Lender/Servicer", "party_b": "Student Borrower", "relationship": "educational lending"},
        ContractType.EMPLOYMENT: {"party_a": "Employer", "party_b": "Employee", "relationship": "employment"},
        ContractType.NDA: {"party_a": "Disclosing Party", "party_b": "Receiving Party", "relationship": "confidentiality"},
        ContractType.SERVICE_AGREEMENT: {"party_a": "Client", "party_b": "Vendor/Service Provider", "relationship": "services"},
        ContractType.LEASE: {"party_a": "Lessor/Landlord", "party_b": "Lessee/Tenant", "relationship": "lease"},
        ContractType.OTHER: {"party_a": "Party A", "party_b": "Party B", "relationship": "contractual"},
    }
    return party_map.get(contract_type, party_map[ContractType.OTHER])


def detect_document_issues(text: str) -> list:
    """Pre-audit structural checks."""
    issues = []

    # Blank/placeholder fields
    blank_fields = re.findall(r'(_{2,}|\.{3,}|\[.*?\]|\(.*?\)|___+|\.\.\.+)', text)
    if blank_fields:
        issues.append({
            "type": "incomplete_document",
            "severity": "HIGH",
            "detail": f"Document contains {len(blank_fields)} blank/placeholder field(s) that should be filled before execution.",
            "examples": blank_fields[:5]
        })

    # Missing signatures
    has_signature_block = re.search(r'(signature|signed|sign)\s*:?', text, re.IGNORECASE)
    has_date_block = re.search(r'date\s*:?\s*_{0,3}\s*\n', text, re.IGNORECASE)
    if has_signature_block and not re.search(r'[A-Z][a-z]+.*_{3,}', text):
        issues.append({
            "type": "missing_signatures",
            "severity": "CRITICAL",
            "detail": "Signature block present but no signatures filled in. Contract may be unenforceable."
        })

    # PII
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
        issues.append({
            "type": "exposed_pii",
            "severity": "CRITICAL",
            "detail": "Social Security Number found in plain text. Redact before sharing."
        })
    if re.search(r'\b\d{2}/\d{2}/\d{4}\b', text):
        issues.append({
            "type": "exposed_pii",
            "severity": "HIGH",
            "detail": "Date of birth in plain text detected. Verify if intentional."
        })

    # Missing governing law
    if not re.search(r'govern(ing|ed)\s+(by|law|under)', text, re.IGNORECASE):
        issues.append({
            "type": "missing_governing_law",
            "severity": "MEDIUM",
            "detail": "No governing law or jurisdiction specified. In case of dispute, applicable law will be uncertain."
        })

    return issues
