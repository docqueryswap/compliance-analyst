import json
import time
import requests
import os
from datetime import datetime
from typing import Dict, Any

SPACE_URL = os.getenv("SPACE_URL", "https://docqueryswap-compliance-analyst.hf.space")
AUDIT_ENDPOINT = f"{SPACE_URL}/audit"
UPLOAD_ENDPOINT = f"{SPACE_URL}/upload"

TEST_CASES_FILE = "evaluation/test_cases.json"
REPORT_OUTPUT = "evaluation/evaluation_report.json"

def upload_document(file_path: str) -> str:
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(UPLOAD_ENDPOINT, files=files, timeout=60)
        response.raise_for_status()
        return response.json()["client_id"]

def run_audit(client_id: str) -> Dict[str, Any]:
    response = requests.post(AUDIT_ENDPOINT, json={"client_id": client_id}, timeout=120)
    response.raise_for_status()
    return response.json()

def infer_document_type(audit: Dict[str, Any]) -> str:
    """Infer document type from plan or draft report content."""
    # First, check if the field exists (in case you later add it)
    if "document_type" in audit:
        return audit["document_type"]
    
    # Look at plan items and draft report for keywords
    plan = audit.get("plan", [])
    draft = audit.get("draft_report", "").lower()
    plan_text = " ".join(plan).lower()
    
    contract_keywords = ["contract", "agreement", "termination", "clause", "obligation"]
    resume_keywords = ["resume", "skills", "experience", "education", "job"]
    policy_keywords = ["policy", "compliance", "regulation", "guideline"]
    
    # Check draft report first (more reliable)
    for kw in contract_keywords:
        if kw in draft:
            return "contract"
    for kw in resume_keywords:
        if kw in draft:
            return "resume"
    for kw in policy_keywords:
        if kw in draft:
            return "policy"
    
    # Fallback to plan text
    if any(kw in plan_text for kw in contract_keywords):
        return "contract"
    if any(kw in plan_text for kw in resume_keywords):
        return "resume"
    if any(kw in plan_text for kw in policy_keywords):
        return "policy"
    
    return "other"

def evaluate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    result = {
        "id": case["id"],
        "timestamp": datetime.utcnow().isoformat(),
        "success": False,
        "latency_sec": 0,
        "failure_reason": None,
        "doc_type_match": False,
        "keywords_present": [],
    }
    try:
        client_id = upload_document(case["document_path"])
        audit = run_audit(client_id)
        draft = audit.get("draft_report", "")
        
        # Infer document type instead of relying on a missing field
        detected_type = infer_document_type(audit)
        result["doc_type_match"] = (detected_type == case["expected_doc_type"])
        
        keywords_found = [kw for kw in case.get("should_contain_keywords", []) if kw.lower() in draft.lower()]
        result["keywords_present"] = keywords_found
        all_keywords = len(keywords_found) == len(case.get("should_contain_keywords", []))
        result["success"] = result["doc_type_match"] and all_keywords
    except Exception as e:
        result["failure_reason"] = str(e)
    result["latency_sec"] = round(time.time() - start, 2)
    return result

def main():
    print("🚀 Starting Compliance Analyst Evaluation...")
    with open(TEST_CASES_FILE, "r") as f:
        test_cases = json.load(f)
    results = [evaluate_case(case) for case in test_cases]
    total = len(results)
    successes = sum(1 for r in results if r["success"])
    accuracy = successes / total if total else 0
    avg_latency = sum(r["latency_sec"] for r in results) / total if total else 0

    print("\n" + "="*50)
    print("📊 EVALUATION SUMMARY")
    print("="*50)
    print(f"Accuracy: {accuracy*100:.1f}% ({successes}/{total})")
    print(f"Avg latency: {avg_latency:.2f}s")

    report = {
        "summary": {"accuracy": accuracy, "avg_latency": avg_latency, "total": total},
        "results": results
    }
    with open(REPORT_OUTPUT, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n📁 Report saved to {REPORT_OUTPUT}")

if __name__ == "__main__":
    main()
