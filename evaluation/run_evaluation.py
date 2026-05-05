import json
import time
import requests
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    if "document_type" in audit:
        return audit["document_type"]
    
    draft = audit.get("draft_report", "").lower()
    
    if "cannot audit" in draft:
        return "non_auditable"
    
    type_keywords = {
        "consumer_loan": ["lender", "borrower", "usury", "collateral", "repossession"],
        "employment": ["employee", "employer", "working hours", "leave", "overtime"],
        "service_agreement": ["vendor", "scope of engagement", "service provider", "deliverable"],
        "nda": ["confidential", "non-disclosure", "trade secret"],
        "lease": ["landlord", "tenant", "lease", "security deposit"],
        "student_loan": ["student loan", "education", "deferment", "forbearance"],
    }
    
    scores = {}
    for doc_type, keywords in type_keywords.items():
        scores[doc_type] = sum(1 for kw in keywords if kw in draft)
    
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] >= 2:
            return best
    
    return "other"


def evaluate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    result = {
        "id": case["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": False,
        "latency_sec": 0,
        "failure_reason": None,
        "doc_type_match": False,
        "detected_type": None,
        "keywords_present": [],
        "unwanted_keywords_found": [],
    }
    
    try:
        client_id = upload_document(case["document_path"])
        audit = run_audit(client_id)
        draft = audit.get("draft_report", "")
        
        detected_type = infer_document_type(audit)
        result["detected_type"] = detected_type
        result["doc_type_match"] = (detected_type == case["expected_doc_type"])
        
        keywords_found = [
            kw for kw in case.get("should_contain_keywords", [])
            if kw.lower() in draft.lower()
        ]
        result["keywords_present"] = keywords_found
        all_required = len(keywords_found) == len(case.get("should_contain_keywords", []))
        
        unwanted_found = [
            kw for kw in case.get("should_not_contain_keywords", [])
            if kw.lower() in draft.lower()
        ]
        result["unwanted_keywords_found"] = unwanted_found
        no_contamination = len(unwanted_found) == 0
        
        result["success"] = result["doc_type_match"] and all_required and no_contamination
        
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
    
    print("\n" + "=" * 60)
    print("📊 EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Accuracy: {accuracy*100:.1f}% ({successes}/{total})")
    print(f"Avg latency: {avg_latency:.2f}s")
    print()
    
    for r in results:
        status = "✅" if r["success"] else "❌"
        expected = r.get("expected_type", case.get("expected_doc_type", "N/A"))
        print(f"{status} {r['id']}: type={r.get('detected_type', 'N/A')} "
              f"(expected {expected}) "
              f"latency={r['latency_sec']}s")
        if not r["success"]:
            if not r.get("doc_type_match"):
                print(f"   ⚠️ Type mismatch: got '{r.get('detected_type')}', "
                      f"expected '{expected}'")
            if r.get("unwanted_keywords_found"):
                print(f"   ⚠️ Cross-contamination: found {r['unwanted_keywords_found']}")
            if r.get("failure_reason"):
                print(f"   ⚠️ Error: {r['failure_reason']}")
    
    report = {
        "summary": {
            "accuracy": accuracy,
            "avg_latency": avg_latency,
            "total": total,
            "successes": successes
        },
        "results": results
    }
    
    with open(REPORT_OUTPUT, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📁 Report saved to {REPORT_OUTPUT}")
    
    if successes < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
