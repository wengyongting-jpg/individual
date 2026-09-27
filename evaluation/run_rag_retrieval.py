"""
evaluation/run_rag_retrieval.py
===============================

STAGE 2 — Run all 22 ground-truth questions through the RAG RETRIEVAL layer
and save the results. RETRIEVAL ONLY: no Foundation Model, no abstention.

What this does
--------------
1. Loads the LOCKED ground truth (read-only; never modified).
2. Runs each of the 20 questions through the TF-IDF + cosine retriever.
3. Saves per-case retrieval output to
   ``evaluation/results/rag_retrieval_results.json``.
4. Prints objective retrieval metrics.

Guardrails (per project rules)
-------------------------------
* ``expected_action`` and ``expected_source`` are copied from the ground truth
  ONLY as reference fields for later comparison. The retriever NEVER sees them
  and does not use them to decide what to retrieve.
* Retrieval is not the final answer, so we call the metric a RETRIEVAL HIT
  RATE, never "answer correctness".
* Nothing is tuned to individual test cases.

Run with:
    python evaluation/run_rag_retrieval.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "rag"))

from retriever import build_retriever  # noqa: E402


GROUND_TRUTH_PATH = os.path.join(REPO_ROOT, "ground_truth.json")
RESULTS_DIR = os.path.join(HERE, "results")
RESULTS_PATH = os.path.join(RESULTS_DIR, "rag_retrieval_results.json")

# Same small fixed TOP_K used across the project for a fair comparison.
TOP_K = 3


def load_ground_truth(path: str = GROUND_TRUTH_PATH) -> Dict:
    """Load the locked ground truth. READ ONLY."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Ground truth not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run() -> Dict:
    gt = load_ground_truth()
    test_cases = gt["test_cases"]

    retriever = build_retriever()

    per_case: List[Dict] = []
    for case in test_cases:
        question = case["question"]
        expected_source = case.get("expected_source", [])

        out = retriever.retrieve(question, top_k=TOP_K)
        passages = out["retrieved_passages"]

        top_source = passages[0]["source"] if passages else None
        top_score = passages[0]["score"] if passages else 0.0

        retrieved_sources: List[str] = []
        for p in passages:
            if p["source"] not in retrieved_sources:
                retrieved_sources.append(p["source"])

        has_expected = len(expected_source) > 0
        top_source_hit = (top_source in expected_source) if has_expected else None
        any_source_hit = (
            any(s in expected_source for s in retrieved_sources)
            if has_expected else None
        )

        per_case.append(
            {
                "test_case_id": case["test_case_id"],
                "question": question,
                "category": case["category"],
                # reference fields from ground truth (NOT used by retrieval):
                "expected_action": case["expected_action"],
                "expected_source": expected_source,
                # retrieval output:
                "system": "rag_retrieval",
                "retrieval_method": out["retrieval_method"],
                "retrieved_passages": passages,
                "retrieved_sources": retrieved_sources,
                "top_source": top_source,
                "top_score": top_score,
                "latency_ms": out["latency_ms"],
                # objective retrieval facts:
                "top_source_hit": top_source_hit,
                "any_source_hit": any_source_hit,
            }
        )

    metrics = compute_metrics(per_case)

    return {
        "_meta": {
            "stage": "Stage 2 — RAG retrieval (retrieval only, no LLM)",
            "system": "rag_retrieval",
            "retrieval_method": retriever.retrieval_method,
            "score_meaning": (
                "cosine similarity in [0,1] between the question TF-IDF vector "
                "and a chunk TF-IDF vector; a lexical/semantic similarity, NOT a "
                "probability or confidence."
            ),
            "top_k": TOP_K,
            "num_documents": retriever.num_documents,
            "num_chunks": retriever.num_chunks,
            "foundation_model_called": False,
            "abstention_implemented": False,
            "ground_truth_locked": gt["_meta"].get("locked"),
            "ground_truth_num_cases": gt["_meta"].get("num_cases"),
        },
        "metrics": metrics,
        "results": per_case,
    }


def compute_metrics(per_case: List[Dict]) -> Dict:
    latencies = [c["latency_ms"] for c in per_case]

    scorable = [c for c in per_case if len(c["expected_source"]) > 0]
    top_hits = [c for c in scorable if c["top_source_hit"]]
    any_hits = [c for c in scorable if c["any_source_hit"]]

    no_source = [c for c in per_case if len(c["expected_source"]) == 0]

    def rate(n: int, d: int) -> float:
        return round(n / d, 4) if d else 0.0

    return {
        "total_cases": len(per_case),
        "latency_ms": {
            "per_case": {c["test_case_id"]: c["latency_ms"] for c in per_case},
            "median": round(statistics.median(latencies), 4) if latencies else 0.0,
            "mean": round(statistics.mean(latencies), 4) if latencies else 0.0,
            "min": round(min(latencies), 4) if latencies else 0.0,
            "max": round(max(latencies), 4) if latencies else 0.0,
        },
        "retrieval_hit_rate": {
            "note": (
                "Retrieval hit rate ONLY (not answer correctness). Defined only "
                "for cases with a non-empty expected_source."
            ),
            "scorable_cases": len(scorable),
            "top1_source_hits": len(top_hits),
            "top1_source_hit_rate": rate(len(top_hits), len(scorable)),
            "top3_source_hits": len(any_hits),
            "top3_source_hit_rate": rate(len(any_hits), len(scorable)),
        },
        "insufficient_evidence_cases": {
            "note": (
                "expected_source is empty (no correct document). We report the "
                "top cosine score each still retrieves, to show whether the "
                "retriever surfaces near-miss passages. This informs the later "
                "abstention threshold; NO threshold is applied here."
            ),
            "count": len(no_source),
            "top_scores": {c["test_case_id"]: c["top_score"] for c in no_source},
        },
    }


def save_results(payload: Dict, path: str = RESULTS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def print_summary(payload: Dict) -> None:
    meta = payload["_meta"]
    m = payload["metrics"]
    line = "=" * 82

    print(line)
    print("STAGE 2 — RAG RETRIEVAL (retrieval only, no Foundation Model)")
    print(line)
    print(f"Retrieval method : {meta['retrieval_method']}")
    print(f"Documents/chunks : {meta['num_documents']} docs / {meta['num_chunks']} chunks")
    print(f"top_k            : {meta['top_k']}")
    print(f"Ground truth     : locked={meta['ground_truth_locked']}, "
          f"cases={meta['ground_truth_num_cases']}")
    print(line)

    print(f"{'CASE':<6}{'CATEGORY':<22}{'EXP_ACTION':<22}"
          f"{'TOP1_HIT':<10}{'TOP_SCORE':>10}{'LAT(ms)':>9}")
    print("-" * 82)
    for c in payload["results"]:
        hit = c["top_source_hit"]
        hit_str = "n/a" if hit is None else ("yes" if hit else "no")
        print(f"{c['test_case_id']:<6}{c['category']:<22}"
              f"{c['expected_action']:<22}{hit_str:<10}"
              f"{c['top_score']:>10}{c['latency_ms']:>9}")
    print("-" * 82)

    lat = m["latency_ms"]
    print(f"Total cases       : {m['total_cases']}")
    print(f"Latency median    : {lat['median']} ms")
    print(f"Latency mean      : {lat['mean']} ms")
    print(f"Latency min / max : {lat['min']} / {lat['max']} ms")

    hr = m["retrieval_hit_rate"]
    print(line)
    print("RETRIEVAL HIT RATE (cases with a non-empty expected_source)")
    print(f"  Scorable cases        : {hr['scorable_cases']}")
    print(f"  Top-1 source hit rate : {hr['top1_source_hits']}/"
          f"{hr['scorable_cases']} = {hr['top1_source_hit_rate']}")
    print(f"  Top-3 source hit rate : {hr['top3_source_hits']}/"
          f"{hr['scorable_cases']} = {hr['top3_source_hit_rate']}")

    ie = m["insufficient_evidence_cases"]
    print(line)
    print("INSUFFICIENT-EVIDENCE CASES (empty expected_source) — top cosine score")
    for tc, sc in ie["top_scores"].items():
        print(f"  {tc}: top_score={sc}")
    print(line)
    print(f"Saved results to: {RESULTS_PATH}")


def main() -> None:
    payload = run()
    save_results(payload)
    print_summary(payload)


if __name__ == "__main__":
    main()
