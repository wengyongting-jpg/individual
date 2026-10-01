"""
evaluation/analyze_user_study.py
================================

Analyses the independent user-study measurements and writes
evaluation/results/user_study_summary.json, which evaluation/compare.py then
picks up as the project's SECONDARY metric (median task-completion time).

Input : evaluation/results/user_study_results.csv
         Columns: participant_id, question_id, method (manual|rag),
                  completion_time_seconds, correct (true|false)
         See docs/user_study_protocol.md for the collection protocol.

Output: evaluation/results/user_study_summary.json

Honesty rule: this script only aggregates what is actually in the CSV. If the
CSV has no data rows, the summary is written with status
OPTIONAL_EXTENSION_NOT_CONDUCTED and no medians are fabricated. If the measured
reduction is below the 50% target, it is reported as-is.

Run:
    python evaluation/analyze_user_study.py
"""

from __future__ import annotations

import csv
import json
import os
import statistics
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
CSV_PATH = os.path.join(RESULTS_DIR, "user_study_results.csv")
SUMMARY_PATH = os.path.join(RESULTS_DIR, "user_study_summary.json")

# Project target from the Problem Statement: the RAG assistant should reduce
# median task-completion time by at least 50% vs manual keyword search.
TARGET_REDUCTION_PCT = 50.0

EXPECTED_COLUMNS = [
    "participant_id",
    "question_id",
    "method",
    "completion_time_seconds",
    "correct",
]


def load_rows(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in EXPECTED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"{os.path.basename(path)} is missing columns: {missing}. "
                f"Expected: {EXPECTED_COLUMNS}"
            )
        return [row for row in reader if any((v or "").strip() for v in row.values())]


def method_stats(rows: List[Dict], method: str) -> Dict:
    sel = [r for r in rows if r["method"].strip().lower() == method]
    times = [float(r["completion_time_seconds"]) for r in sel]
    correct = [r["correct"].strip().lower() == "true" for r in sel]
    return {
        "attempts": len(sel),
        "median_time_seconds": round(statistics.median(times), 2) if times else None,
        "accuracy": round(sum(correct) / len(correct), 4) if correct else None,
    }


def main() -> None:
    base = {
        "metric": "median task-completion time (human, wall-clock)",
        "protocol": "docs/user_study_protocol.md",
        "data_file": "evaluation/results/user_study_results.csv",
        "target": (
            f"reduce median task-completion time by >= {TARGET_REDUCTION_PCT:.0f}% "
            "vs the keyword-search baseline (tested, not assumed)"
        ),
        "honesty_note": (
            "All figures are aggregated from the recorded rows only. No data "
            "points were added, removed, or adjusted to reach the target."
        ),
    }

    optional_note = (
        "The participant study is an optional extension; human-subject "
        "evaluation was not required for the current evaluation, and no "
        "participant data were collected."
    )

    if not os.path.exists(CSV_PATH):
        base["status"] = "OPTIONAL_EXTENSION_NOT_CONDUCTED"
        base["detail"] = f"Data file not found: {CSV_PATH}. " + optional_note
        write(base)
        return

    rows = load_rows(CSV_PATH)
    if not rows:
        base["status"] = "OPTIONAL_EXTENSION_NOT_CONDUCTED"
        base["detail"] = (
            "The CSV contains headers only. No results are reported because "
            "no participant data exist. " + optional_note
        )
        write(base)
        return

    manual = method_stats(rows, "manual")
    rag = method_stats(rows, "rag")
    participants = sorted({r["participant_id"].strip() for r in rows})

    reduction = None
  if (
    manual["median_time_seconds"] is not None
    and rag["median_time_seconds"] is not None
):
        reduction = round(
            (manual["median_time_seconds"] - rag["median_time_seconds"])
            / manual["median_time_seconds"] * 100.0,
            2,
        )

    base.update({
        "status": "MEASURED",
        "participants": participants,
        "n_participants": len(participants),
        "median_manual_time_seconds": manual["median_time_seconds"],
        "median_rag_time_seconds": rag["median_time_seconds"],
        "median_time_reduction_pct": reduction,
        "accuracy_manual": manual["accuracy"],
        "accuracy_rag": rag["accuracy"],
        "attempts_manual": manual["attempts"],
        "attempts_rag": rag["attempts"],
        "target_met": (
            None if reduction is None else reduction >= TARGET_REDUCTION_PCT
        ),
        "sample_size_limitation": (
            f"n={len(participants)} independent participants is a small "
            "sample; treat the measured effect as indicative, not definitive."
        ),
    })
    write(base)


def write(summary: Dict) -> None:
    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("Wrote user-study summary to:", SUMMARY_PATH)
    print("Status:", summary["status"])
    if summary["status"] == "MEASURED":
        print("Participants:", ", ".join(summary["participants"]))
        print("Median manual time (s):", summary["median_manual_time_seconds"])
        print("Median RAG time (s):", summary["median_rag_time_seconds"])
        print("Median time reduction (%):", summary["median_time_reduction_pct"])
        print("Accuracy manual / RAG:",
              summary["accuracy_manual"], "/", summary["accuracy_rag"])
        print("Target (>=50% reduction) met:", summary["target_met"])


if __name__ == "__main__":
    main()
