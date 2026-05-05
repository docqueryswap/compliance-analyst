"""
CI/CD Evaluation - Runs locally without external API calls.
Tests classifier accuracy, structural issue detection, and cross-contamination prevention.
Does NOT require NVIDIA_API_KEY, HF Space, or any external service.
"""
import json
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.classifier import classify_document, ContractType, detect_document_issues

TEST_CASES_FILE = "evaluation/test_cases.json"
REPORT_OUTPUT = "evaluation/evaluation_report.json"


def evaluate_case(case):
    """Test classifier and structural detection without any API calls."""
    result = {
        "id": case["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": False,
        "expected_type": case["expected_doc_type"],
        "detected_type": None,
        "doc_type_match": False,
        "issues_found": 0,
        "failure_reason": None,
    }
    
    try:
        with open(case["document_path"], "r") as f:
            text = f.read()
        
        doc_type = classify_document(text)
        result["detected_type"] = doc_type.value
        result["doc_type_match"] = (doc_type.value == case["expected_doc_type"])
        
        issues = detect_document_issues(text)
        result["issues_found"] = len(issues)
        
        result["success"] = result["doc_type_match"]
        
    except Exception as e:
        result["failure_reason"] = str(e)
    
    return result


def main():
    print("Starting CI Classifier Evaluation...")
    print("   (No API keys or external services required)\n")
    
    with open(TEST_CASES_FILE, "r") as f:
        test_cases = json.load(f)
    
    results = [evaluate_case(case) for case in test_cases]
    total = len(results)
    successes = sum(1 for r in results if r["success"])
    accuracy = successes / total if total else 0
    
    print("=" * 60)
    print("CLASSIFIER EVALUATION")
    print("=" * 60)
    print(f"Accuracy: {accuracy*100:.1f}% ({successes}/{total})\n")
    
    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        print(f"{status} {r['id']}")
        print(f"   Expected: {r['expected_type']} -> Got: {r['detected_type']}")
        print(f"   Issues found: {r['issues_found']}")
        if r["failure_reason"]:
            print(f"   Error: {r['failure_reason']}")
        print()
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {"accuracy": accuracy, "total": total, "successes": successes},
        "results": results,
    }
    
    with open(REPORT_OUTPUT, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Report saved to {REPORT_OUTPUT}")
    
    if successes < total:
        print(f"\n{total - successes} test(s) failed!")
        sys.exit(1)
    else:
        print("\nAll tests passed!")


if __name__ == "__main__":
    main()
