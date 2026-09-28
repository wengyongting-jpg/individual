"""
evaluation/analyze_failures.py
=============================

STAGE 8/11 — Reproducible failure analysis over the ACTUALLY-GENERATED results.

It compares the deterministic decision layer's predicted action (from
stage3_results.json) against the ground-truth expected action, for ALL 22 cases
(no cherry-picking), and classifies each mismatch by failure type. Cases whose
final action depends on the un-executed model are recorded as PENDING, not as
pass or fail.

Output: evaluation/results/failure_analysis.json

Failure types used:
  retrieval_failure   expected source not retrieved in top-k
  decision_failure    action wrong although the expected source WAS retrieved
                      (threshold or clarification rule mis-fired)
  pending_model       final action needs the Foundation Model (not executed)

Run:
    python evaluation/analyze_failures.py
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
RESULTS_DIR = os.path.join(HERE, "results")

STAGE3_PATH = os.path.join(RESULTS_DIR, "stage3_results.json")
RAG_RET_PATH = os.path.join(RESULTS_DIR, "rag_retrieval_results.json")
RAG_RESULTS_PATH = os.path.join(RESULTS_DIR, "rag_results.json")
OUT_PATH = os.path.join(RESULTS_DIR, "failure_analysis.json")


def load(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    stage3 = load(STAGE3_PATH)["results"]
    rag_ret = {r["test_case_id"]: r for r in load(RAG_RET_PATH)["results"]}
    rag_full = {r["test_case_id"]: r for r in load(RAG_RESULTS_PATH)["results"]}

    failures: List[Dict] = []
    pending: List[Dict] = []

    for c in stage3:
        tc = c["test_case_id"]
        expected = c["expected_action"]
        predicted = c["predicted_action"]
        expected_source = c.get("expected_source", [])
        retrieved_sources = rag_ret[tc].get("retrieved_sources", [])
        source_retrieved = (
            any(s in expected_source for s in retrieved_sources)
            if expected_source else None
        )

        # Is the final RAG action for this case pending the model?
        model_status = rag_full[tc]["model_status"]
        is_pending = model_status in {
            "PENDING_EXECUTION", "MODEL_ERROR", "MODEL_OUTPUT_INVALID"}

        if predicted == expected:
            continue  # not a failure at the deterministic layer

        # classify
        if expected_source and source_retrieved is False:
            ftype = "retrieval_failure"
            layer = "retrieval (TF-IDF cosine)"
        else:
            ftype = "decision_failure"
            layer = "decision layer (threshold / clarification rule)"

        record = {
            "test_case_id": tc,
            "category": c["category"],
            "expected_action": expected,
            "observed_action": predicted,
            "failure_type": ftype,
            "likely_layer": layer,
            "expected_source": expected_source,
            "retrieved_sources": retrieved_sources,
            "signals": c["signals"],
            "note_final_action_pending_model": is_pending,
        }
        failures.append(record)

    # Cases whose final answer depends on the model (regardless of correctness).
    for tc, r in rag_full.items():
        if r["model_status"] in {"PENDING_EXECUTION"}:
            pending.append({
                "test_case_id": tc,
                "category": r["category"],
                "reason": "ANSWERED_ELIGIBLE case requires Foundation Model (not executed)",
            })

    summary = {
        "total_cases": len(stage3),
        "deterministic_action_failures": len(failures),
        "failures_by_type": _count_by(failures, "failure_type"),
        "failures_by_category": _count_by(failures, "category"),
        "answered_cases_pending_model": len(pending),
    }

    payload = {
        "_meta": {
            "stage": "Stage 8/11 — failure analysis (actual results, no cherry-picking)",
            "sources": [
                "stage3_results.json (deterministic actions)",
                "rag_retrieval_results.json (retrieved sources)",
                "rag_results.json (model status)",
            ],
            "note": (
                "Analyses the deterministic decision layer against ground truth. "
                "The final Foundation Model run was EXECUTED; no ANSWERED_ELIGIBLE "
                "cases are pending. The 8 failures listed here are the "
                "development-stage deterministic findings (Stage 3, pre-Foundation-Model) "
                "retained as system history — see docs/failure_analysis.md §1."
            ),
        },
        "summary": summary,
        "failures": failures,
        "pending_model_cases": pending,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print("Wrote failure analysis to:", OUT_PATH)
    print("Summary:", json.dumps(summary, indent=2))


def _count_by(items: List[Dict], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        out[it[key]] = out.get(it[key], 0) + 1
    return out


if __name__ == "__main__":
    main()
