"""
evaluation/run_stage3.py
========================

STAGE 3 — Run the 22 HELD-OUT ground-truth cases through the deterministic
decision layer (retrieval -> signals -> clarification/abstention) and MEASURE
how well the predicted ACTION matches the expected action.

Strict guardrails
-----------------
  * The ground truth is used ONLY for measurement here. It was NOT used to
    choose the thresholds (those came from the separate calibration set).
  * No Foundation Model, no API. The decision layer emits a routing decision,
    not a generated answer.
  * Nothing is tuned to individual test cases.

Action mapping
--------------
The decision layer emits ANSWERED_ELIGIBLE to mean "evidence is strong/focused
enough and the question is specific enough that a later stage MAY answer". For
comparison with the ground-truth action vocabulary, ANSWERED_ELIGIBLE is mapped
to ANSWERED. This measures the ROUTING decision (answer vs clarify vs abstain),
NOT final answer correctness — there is no answer generated at Stage 3.

Run:
    python evaluation/run_stage3.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "rag"))

from rag_pipeline import RagPipeline  # noqa: E402
from thresholds import CALIBRATION_PROVENANCE  # noqa: E402

GROUND_TRUTH_PATH = os.path.join(REPO_ROOT, "ground_truth.json")
RESULTS_DIR = os.path.join(HERE, "results")
RESULTS_PATH = os.path.join(RESULTS_DIR, "stage3_results.json")

# Map the decision layer's routing label -> ground-truth action vocabulary.
ACTION_MAP = {
    "ANSWERED_ELIGIBLE": "ANSWERED",
    "CLARIFICATION_REQUIRED": "CLARIFICATION_REQUIRED",
    "ABSTAIN": "ABSTAIN",
}


def load_ground_truth(path: str = GROUND_TRUTH_PATH) -> Dict:
    """Load the locked ground truth. READ ONLY."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run() -> Dict:
    gt = load_ground_truth()
    pipe = RagPipeline()

    per_case: List[Dict] = []
    for case in gt["test_cases"]:
        out = pipe.run(case["question"])
        predicted_action = ACTION_MAP[out["action"]]
        expected_action = case["expected_action"]

        per_case.append(
            {
                "test_case_id": case["test_case_id"],
                "question": case["question"],
                "category": case["category"],
                "expected_action": expected_action,
                "expected_source": case.get("expected_source", []),
                "predicted_action": predicted_action,
                "raw_decision": out["action"],
                "action_correct": predicted_action == expected_action,
                "reason": out["reason"],
                "signals": out["signals"],
                "top_source": out["top_source"],
                "abstain_message": out["abstain_message"],
                "latency_ms": out["latency_ms"],
            }
        )

    metrics = compute_metrics(per_case)

    return {
        "_meta": {
            "stage": "Stage 3 — deterministic clarification + abstention",
            "system": "rag_decision_layer_no_llm",
            "foundation_model_called": False,
            "ground_truth_role": "measurement only (not used to select thresholds)",
            "thresholds": CALIBRATION_PROVENANCE,
            "action_map": ACTION_MAP,
            "note": (
                "predicted_action measures the ROUTING decision (answer vs "
                "clarify vs abstain), NOT final answer correctness. No answer "
                "text is generated at Stage 3."
            ),
        },
        "metrics": metrics,
        "results": per_case,
    }


def compute_metrics(per_case: List[Dict]) -> Dict:
    total = len(per_case)
    correct = sum(1 for c in per_case if c["action_correct"])
    latencies = [c["latency_ms"] for c in per_case]

    # Per-category accuracy.
    by_cat_total: Dict[str, int] = defaultdict(int)
    by_cat_correct: Dict[str, int] = defaultdict(int)
    for c in per_case:
        by_cat_total[c["category"]] += 1
        if c["action_correct"]:
            by_cat_correct[c["category"]] += 1

    # Confusion counts: expected -> predicted.
    confusion: Dict[str, Counter] = defaultdict(Counter)
    for c in per_case:
        confusion[c["expected_action"]][c["predicted_action"]] += 1

    return {
        "total_cases": total,
        "action_accuracy": round(correct / total, 4) if total else 0.0,
        "correct_actions": correct,
        "per_category_accuracy": {
            cat: {
                "correct": by_cat_correct[cat],
                "total": by_cat_total[cat],
                "accuracy": round(by_cat_correct[cat] / by_cat_total[cat], 4),
            }
            for cat in sorted(by_cat_total)
        },
        "confusion_expected_to_predicted": {
            exp: dict(preds) for exp, preds in sorted(confusion.items())
        },
        "latency_ms": {
            "median": round(statistics.median(latencies), 4) if latencies else 0.0,
            "mean": round(statistics.mean(latencies), 4) if latencies else 0.0,
        },
    }


def save_results(payload: Dict, path: str = RESULTS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def print_summary(payload: Dict) -> None:
    m = payload["metrics"]
    line = "=" * 88
    print(line)
    print("STAGE 3 — DECISION LAYER ON 22 HELD-OUT GROUND-TRUTH CASES (measurement only)")
    print(line)
    print(f"{'CASE':<6}{'CATEGORY':<22}{'EXPECTED':<22}{'PREDICTED':<22}{'OK':<4}")
    print("-" * 88)
    for c in payload["results"]:
        print(f"{c['test_case_id']:<6}{c['category']:<22}"
              f"{c['expected_action']:<22}{c['predicted_action']:<22}"
              f"{'Y' if c['action_correct'] else 'N':<4}")
    print("-" * 88)
    print(f"Action accuracy : {m['correct_actions']}/{m['total_cases']} "
          f"= {m['action_accuracy']}")
    print("Per-category accuracy:")
    for cat, s in m["per_category_accuracy"].items():
        print(f"  {cat:<22} {s['correct']}/{s['total']} = {s['accuracy']}")
    print("Confusion (expected -> predicted):")
    for exp, preds in m["confusion_expected_to_predicted"].items():
        print(f"  {exp:<22} -> {preds}")
    print(f"Latency median  : {m['latency_ms']['median']} ms")
    print(line)
    print(f"Saved results to: {RESULTS_PATH}")


def main() -> None:
    payload = run()
    save_results(payload)
    print_summary(payload)


if __name__ == "__main__":
    main()
