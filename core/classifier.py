"""
Document type classifier using rule-based pattern matching.
Fast, deterministic, and extensible.
"""
import re
from enum import Enum
from typing import Optional


class ContractType(str, Enum):
    CONSUMER_LOAN = "consumer_loan"
    STUDENT_LOAN = "student_loan"
    EMPLOYMENT = "employment"
    NDA = "nda"
    SERVICE_AGREEMENT = "service_agreement"
    LEASE = "lease"
    OTHER = "other"


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


def classify_document(text: str) -> ContractType:
    """
    Classify a document by scoring regex patterns.
    Returns the highest-scoring contract type.
    """
    text_lower = text.lower()
    scores = {ct: 0.0 for ct in ContractType}
    
    for pattern, contract_type, boost in CLASSIFICATION_RULES:
        if re.search(pattern, text_lower):
            scores[contract_type] += boost
    
    # Find the highest scoring type
    best_type = max(scores, key=scores.get)
    
    # If no strong signal, default to OTHER
    if scores[best_type] < 0.5:
        return ContractType.OTHER
    
    return best_type


def get_party_labels(contract_type: ContractType) -> dict:
    """
    Returns the expected party role labels for a given contract type.
    Used to help the executor interpret terms correctly.
    """
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
    """
    Pre-audit checks: detect blank fields, missing signatures, exposed PII.
    Returns a list of structural issues found.
    """
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
    
    # Exposed PII (SSN, DOB, passport numbers)
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