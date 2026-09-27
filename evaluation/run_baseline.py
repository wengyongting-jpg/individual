"""
evaluation/run_baseline.py
==========================

STAGE 1 — Reproducible evaluation runner for the NON-AI keyword-search baseline.

What this script does
---------------------
1. Loads the LOCKED ground truth from ``ground_truth.json`` (read-only; never
   modified by this script).
2. Runs all 22 ground-truth questions through the deterministic keyword-search
   baseline (``baseline/keyword_search.py``) using the SAME 15 policy documents
   that the future RAG system will use.
3. Saves the per-case results to ``evaluation/results/baseline_results.json``.
4. Prints Stage-1 metrics: total cases, per-case latency, median latency, and
   an objectively-measurable retrieval hit rate.

Important design notes (per project rules)
------------------------------------------
* The keyword baseline is a PURE RETRIEVAL system. It has no language model and
  therefore cannot, on its own, decide ANSWERED / CLARIFICATION_REQUIRED /
  ABSTAIN. This script does NOT invent an answer or an action for it. It records
  the *retrieval outcome* factually (which passages/sources were retrieved, the
  scores, whether anything matched at all).
* ``expected_action`` and ``expected_source`` are copied from the ground truth
  ONLY as reference fields, so the common evaluation harness (Stage 6) can line
  results up against the ground truth later. The baseline never sees the
  expected answer and nothing here is tuned to individual test cases.
* Retrieval hit rate is only defined where it is objectively measurable: cases
  whose ground truth lists a non-empty ``expected_source``. The 5
  insufficient-evidence cases (empty ``expected_source``) have no "correct"
  document to retrieve, so they are reported separately, not scored as hits.

Run it with:

    python evaluation/run_baseline.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from typing import Dict, List

# Make the sibling ``baseline`` package importable regardless of where this
# script is launched from.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "baseline"))

from keyword_search import KeywordSearch  # noqa: E402  (import after path setup)


GROUND_TRUTH_PATH = os.path.join(REPO_ROOT, "ground_truth.json")
RESULTS_DIR = os.path.join(HERE, "results")
RESULTS_PATH = os.path.join(RESULTS_DIR, "baseline_results.json")

# How many passages the baseline returns per question. Fixed and reported so
# the run is reproducible; the same value should be reused for a fair RAG
# comparison later.
TOP_K = 3


def load_ground_truth(path: str = GROUND_TRUTH_PATH) -> Dict:
    """Load the locked ground truth. This function only READS the file."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Ground truth not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run_baseline() -> Dict:
    """Run all ground-truth cases through the keyword baseline and collect results."""
    gt = load_ground_truth()
    test_cases = gt["test_cases"]

    engine = KeywordSearch()  # loads + indexes the 15 policy documents once

    per_case: List[Dict] = []

    for case in test_cases:
        tc_id = case["test_case_id"]
        question = case["question"]
        expected_action = case["expected_action"]
        expected_source = case.get("expected_source", [])

        search = engine.search(question, top_k=TOP_K)

        retrieved_passages = [
            {
                "rank": r.rank,
                "score": r.score,
                "source_document": r.source_document,
                "matched_keywords": r.matched_keywords,
                "passage": r.passage,
            }
            for r in search.results
        ]

        top_source = (
            search.results[0].source_document if search.results else None
        )
        # Ordered, de-duplicated list of every source that appears in the top-K.
        retrieved_sources: List[str] = []
        for r in search.results:
            if r.source_document not in retrieved_sources:
                retrieved_sources.append(r.source_document)

        # Objective, non-AI retrieval facts (no invented answer/action):
        #  - retrieval_nonempty: did the baseline match anything at all?
        #  - top_source_hit: is the top-ranked source one of the expected sources?
        #  - any_source_hit: does ANY expected source appear anywhere in top-K?
        # These are only meaningful when expected_source is non-empty; otherwise
        # they are recorded as None (undefined for insufficient-evidence cases).
        has_expected_source = len(expected_source) > 0
        top_source_hit = (
            (top_source in expected_source) if has_expected_source else None
        )
        any_source_hit = (
            any(s in expected_source for s in retrieved_sources)
            if has_expected_source
            else None
        )

        per_case.append(
            {
                "test_case_id": tc_id,
                "question": question,
                "category": case["category"],
                # Reference fields copied from ground truth (NOT predicted here):
                "expected_action": expected_action,
                "expected_source": expected_source,
                # What the deterministic baseline actually produced:
                "system": "keyword_baseline",
                "query_keywords": search.query_keywords,
                "retrieved_passages": retrieved_passages,
                "retrieved_sources": retrieved_sources,
                "top_source": top_source,
                "top_score": (search.results[0].score if search.results else 0.0),
                "latency_ms": search.latency_ms,
                # Objective retrieval outcome (baseline has no LLM, so no
                # ANSWERED/CLARIFICATION/ABSTAIN decision is invented here):
                "retrieval_nonempty": bool(search.results),
                "top_source_hit": top_source_hit,
                "any_source_hit": any_source_hit,
            }
        )

    metrics = compute_metrics(per_case, engine)

    return {
        "_meta": {
            "stage": "Stage 1 — keyword baseline evaluation",
            "system": "keyword_baseline",
            "description": (
                "Deterministic non-AI keyword search over the 15 SynthCorp "
                "policy documents. No LLM, embeddings, or external API. The "
                "baseline is retrieval-only; it does not decide "
                "ANSWERED/CLARIFICATION_REQUIRED/ABSTAIN. expected_action and "
                "expected_source are copied from the locked ground truth for "
                "later comparison only."
            ),
            "top_k": TOP_K,
            "num_documents": engine.num_documents,
            "num_passages": len(engine.passages),
            "ground_truth_locked": load_ground_truth()["_meta"].get("locked"),
            "ground_truth_num_cases": load_ground_truth()["_meta"].get("num_cases"),
        },
        "metrics": metrics,
        "results": per_case,
    }


def compute_metrics(per_case: List[Dict], engine: KeywordSearch) -> Dict:
    """Compute Stage-1 metrics that are objectively measurable for the baseline."""
    latencies = [c["latency_ms"] for c in per_case]

    # Retrieval hit rate is only defined for cases with a non-empty
    # expected_source. Those are exactly the answerable + ambiguous cases.
    scorable = [c for c in per_case if len(c["expected_source"]) > 0]
    top_hits = [c for c in scorable if c["top_source_hit"]]
    any_hits = [c for c in scorable if c["any_source_hit"]]

    # Cases with an empty expected_source (insufficient-evidence). For these the
    # ideal retrieval behaviour is ambiguous for a keyword system, so we only
    # report how often it still returned something (a "near-miss" tendency).
    no_source_cases = [c for c in per_case if len(c["expected_source"]) == 0]
    no_source_nonempty = [c for c in no_source_cases if c["retrieval_nonempty"]]

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
                "Only defined for cases whose ground truth lists a non-empty "
                "expected_source. The 5 insufficient-evidence cases (empty "
                "expected_source) are excluded and reported separately."
            ),
            "scorable_cases": len(scorable),
            "top_source_hits": len(top_hits),
            "top_source_hit_rate": rate(len(top_hits), len(scorable)),
            "any_source_hits": len(any_hits),
            "any_source_hit_rate": rate(len(any_hits), len(scorable)),
        },
        "insufficient_evidence_cases": {
            "note": (
                "expected_source is empty, so there is no 'correct' document to "
                "retrieve. We only report how often the baseline still returned "
                "at least one passage (i.e. would surface a near-miss)."
            ),
            "count": len(no_source_cases),
            "returned_something": len(no_source_nonempty),
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
    line = "=" * 78

    print(line)
    print("STAGE 1 — KEYWORD BASELINE EVALUATION")
    print(line)
    print(f"Documents indexed : {meta['num_documents']}")
    print(f"Passages indexed  : {meta['num_passages']}")
    print(f"top_k             : {meta['top_k']}")
    print(f"Ground truth      : locked={meta['ground_truth_locked']}, "
          f"cases={meta['ground_truth_num_cases']}")
    print(line)

    # Per-case one-line table.
    print(f"{'CASE':<6}{'CATEGORY':<22}{'EXP_ACTION':<22}"
          f"{'TOP_SOURCE_HIT':<16}{'LAT(ms)':>8}")
    print("-" * 78)
    for c in payload["results"]:
        hit = c["top_source_hit"]
        hit_str = "n/a" if hit is None else ("yes" if hit else "no")
        print(f"{c['test_case_id']:<6}{c['category']:<22}"
              f"{c['expected_action']:<22}{hit_str:<16}{c['latency_ms']:>8}")
    print("-" * 78)

    lat = m["latency_ms"]
    print(f"Total cases        : {m['total_cases']}")
    print(f"Latency median     : {lat['median']} ms")
    print(f"Latency mean       : {lat['mean']} ms")
    print(f"Latency min / max  : {lat['min']} / {lat['max']} ms")

    hr = m["retrieval_hit_rate"]
    print(line)
    print("RETRIEVAL HIT RATE (only cases with a non-empty expected_source)")
    print(f"  Scorable cases            : {hr['scorable_cases']}")
    print(f"  Top-source hit rate       : {hr['top_source_hits']}/"
          f"{hr['scorable_cases']} = {hr['top_source_hit_rate']}")
    print(f"  Any-source-in-topK hit    : {hr['any_source_hits']}/"
          f"{hr['scorable_cases']} = {hr['any_source_hit_rate']}")

    ie = m["insufficient_evidence_cases"]
    print(line)
    print("INSUFFICIENT-EVIDENCE CASES (empty expected_source)")
    print(f"  Count                     : {ie['count']}")
    print(f"  Returned >=1 passage      : {ie['returned_something']} "
          f"(baseline cannot abstain on its own)")
    print(line)
    print(f"Saved results to: {RESULTS_PATH}")


def main() -> None:
    payload = run_baseline()
    save_results(payload)
    print_summary(payload)


if __name__ == "__main__":
    main()
