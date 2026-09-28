"""
evaluation/analyze_edge_cases.py
================================

Retrieval edge-case analysis for the PE6201 report. For a fixed set of
interesting ground-truth cases this prints, per case:

  - the edge type under analysis,
  - top-ranked chunk + score under the CURRENT ranking
    (TF-IDF cosine + deterministic numeric/domain bonuses),
  - best chunk from the EXPECTED source + its score,
  - the decision signals (top_score, margin, structured/multi-source flags),
  - predicted action and model status from the final executed run.

Everything is recomputed from the frozen corpus and the saved
rag_results.json - no number is hand-typed in the documentation.

Run:
    python evaluation/analyze_edge_cases.py
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "rag"))

from retriever import build_retriever  # noqa: E402
from signals import compute_signals  # noqa: E402
from decision import decide_action  # noqa: E402

RESULTS = os.path.join(HERE, "results")

# Cases chosen because each exercises a different retrieval edge - selected by
# structural property, not by outcome. Documented in docs/retrieval_edge_cases.md
EDGE_CASES = {
    "TC06": "vocabulary mismatch / distractor (numeric boundary, goods)",
    "TC07": "vocabulary mismatch / distractor (numeric boundary, goods)",
    "TC08": "vocabulary mismatch / distractor (numeric boundary, goods)",
    "TC21": "two documents needed (current + superseded edition)",
    "TC22": "two documents needed (unreconciled cross-document conflict)",
    "TC18": "absent but plausible (insurance/liability - not in corpus)",
    "TC20": "absent but plausible (FX/currency rules - not in corpus)",
}


def main() -> None:
    gt = json.load(open(os.path.join(REPO_ROOT, "ground_truth.json"), encoding="utf-8"))
    cases = {c["test_case_id"]: c for c in gt["test_cases"]}

    rag = json.load(open(os.path.join(RESULTS, "rag_results.json"), encoding="utf-8"))
    final = {r["test_case_id"]: r for r in rag["results"]}

    retriever = build_retriever()

    for tcid, edge in EDGE_CASES.items():
        q = cases[tcid]["question"]
        expected = cases[tcid].get("expected_source", [])
        out = retriever.retrieve(q, top_k=5)
        passages = out["retrieved_passages"]
        decision = decide_action(q, passages)

        print("=" * 78)
        print(f"{tcid}  [{edge}]")
        print(f"Q: {q}")
        print(f"Expected source(s): {expected or '(none - answer not in corpus)'}")
        print("Final-run action:", final[tcid]["predicted_action"],
              "| model:", final[tcid]["model_status"])
        print("Signals:", decision["signals"])
        print("Top-5 retrieved:")
        for p in passages:
            mark = " <== EXPECTED" if p["source"] in expected else ""
            print(f"  rank {p['rank']} {p['score']:.4f}  {p['source']} "
                  f"[num={p.get('numeric_match')}, dom={p.get('domain_match')}]{mark}")
        if expected:
            exp_scores = [p["score"] for p in passages if p["source"] in expected]
            print("Best expected-source chunk in top-5:",
                  f"{max(exp_scores):.4f}" if exp_scores else "NOT IN TOP-5")
        print()


if __name__ == "__main__":
    main()
