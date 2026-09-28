"""
evaluation/run_rag.py
=====================

STAGE 6 — Run the full RAG answer pipeline (retrieval + deterministic decision +
optional Foundation Model) over the 22 HELD-OUT ground-truth test cases and save
the raw system output to evaluation/results/rag_results.json.

This does NOT score anything (that is evaluate.py). It only records what the
system produced. If no API key is configured, ANSWERED_ELIGIBLE cases are
recorded with action "PENDING_EXECUTION" — never a fabricated answer.

Guardrails:
  * Ground truth is read only to obtain the 22 test cases and to copy reference
    fields; it is never used to influence the system's output.
  * No test-case IDs are special-cased.

Run:
    python evaluation/run_rag.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "rag"))

from rag_answer import RagAnswerPipeline  # noqa: E402
from model_client import load_config  # noqa: E402

GROUND_TRUTH_PATH = os.path.join(REPO_ROOT, "ground_truth.json")
RESULTS_DIR = os.path.join(HERE, "results")
RESULTS_PATH = os.path.join(RESULTS_DIR, "rag_results.json")

TOP_K = 5


def load_ground_truth() -> Dict:
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run() -> Dict:
    gt = load_ground_truth()
    pipe = RagAnswerPipeline(top_k=TOP_K)
    cfg = load_config()

    per_case: List[Dict] = []
    for case in gt["test_cases"]:
        out = pipe.answer(case["question"])
        per_case.append({
            "test_case_id": case["test_case_id"],
            "question": case["question"],
            "category": case["category"],
            # reference fields (not used to influence output):
            "expected_action": case["expected_action"],
            "expected_answer": case["expected_answer"],
            "expected_source": case.get("expected_source", []),
            # system output:
            "predicted_action": out["action"],
            "answer": out["answer"],
            "evidence": out["evidence"],
            "citations": out["citations"],
            "confidence": out["confidence"],
            "top_source": out["top_source"],
            "signals": out["signals"],
            "model_status": out["model_status"],
            "retrieval_latency_ms": out["retrieval_latency_ms"],
            "model_latency_ms": out.get("model_latency_ms", 0.0),
            "model_usage": out.get("model_usage", {}),
        })

    actions = Counter(c["predicted_action"] for c in per_case)
    ret_lat = [c["retrieval_latency_ms"] for c in per_case]
    any_pending = any(c["model_status"] == "PENDING_EXECUTION" for c in per_case)

    return {
        "_meta": {
            "stage": "Stage 6 — full RAG pipeline over 22 held-out GT cases",
            "system": "rag_full",
            "top_k": TOP_K,
            "model_config": cfg.public_dict(),
            "model_execution": (
                "PENDING_EXECUTION (no API key configured; ANSWERED_ELIGIBLE "
                "cases were not sent to the model and no answer was fabricated)"
                if any_pending else "EXECUTED"
            ),
            "predicted_action_counts": dict(actions),
            "retrieval_latency_ms_median": round(statistics.median(ret_lat), 4),
            "ground_truth_role": "questions + reference fields only",
        },
        "results": per_case,
    }


def save(payload: Dict) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main() -> None:
    payload = run()
    save(payload)
    m = payload["_meta"]
    print("STAGE 6 — RAG pipeline run over 22 held-out cases")
    print("model execution :", m["model_execution"])
    print("action counts   :", m["predicted_action_counts"])
    print("retrieval median:", m["retrieval_latency_ms_median"], "ms")
    print("saved to        :", RESULTS_PATH)


if __name__ == "__main__":
    main()
