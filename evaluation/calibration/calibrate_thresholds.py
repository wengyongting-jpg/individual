"""
evaluation/calibration/calibrate_thresholds.py
===============================================

STAGE 3 — Calibrate the abstention thresholds on the SEPARATE synthetic
calibration set, then FREEZE them into rag/thresholds.py.

Pre-declared selection rule (fixed BEFORE looking at any numbers):

    TOP_SCORE_MIN = 10th percentile of the in_corpus top_score distribution
    MARGIN_MIN    = 10th percentile of the in_corpus margin  distribution

Rationale: "accept evidence at least as strong as the weakest 90% of genuine
in-corpus hits." The rule is what is fixed in advance; whatever numeric values
it yields are frozen without further nudging.

CRITICAL GUARDRAILS
  * The 22 locked ground-truth cases are NEVER read here. Thresholds are chosen
    only from the calibration set.
  * The percentile rule is not searched for the value that maximises 22-case
    accuracy. It is applied mechanically.
  * We also print the out_of_corpus distribution and the resulting separation,
    purely for transparency / the report — the out_of_corpus numbers do NOT
    change the chosen thresholds (the rule uses only in_corpus percentiles).

Run:
    python evaluation/calibration/calibrate_thresholds.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import date
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "rag"))

from retriever import build_retriever, DEFAULT_TOP_K  # noqa: E402
from signals import compute_signals  # noqa: E402

CALIB_PATH = os.path.join(HERE, "calibration_questions.json")
THRESHOLDS_PATH = os.path.join(REPO_ROOT, "rag", "thresholds.py")

# Pre-declared calibration rule (fixed in advance).
PERCENTILE = 10  # 10th percentile of the in_corpus distribution


def percentile(values: List[float], pct: float) -> float:
    """Deterministic linear-interpolation percentile (numpy-free)."""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    rank = (pct / 100.0) * (len(xs) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(xs) - 1)
    frac = rank - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def describe(values: List[float]) -> Dict[str, float]:
    if not values:
        return {}
    return {
        "n": len(values),
        "min": round(min(values), 6),
        "p10": round(percentile(values, 10), 6),
        "median": round(statistics.median(values), 6),
        "mean": round(statistics.mean(values), 6),
        "max": round(max(values), 6),
    }


def main() -> None:
    with open(CALIB_PATH, "r", encoding="utf-8") as fh:
        calib = json.load(fh)

    retriever = build_retriever()

    in_top, in_margin = [], []
    out_top, out_margin = [], []

    for q in calib["questions"]:
        out = retriever.retrieve(q["question"], top_k=DEFAULT_TOP_K)
        sig = compute_signals(out["retrieved_passages"])
        if q["klass"] == "in_corpus":
            in_top.append(sig["top_score"])
            in_margin.append(sig["margin"])
        else:
            out_top.append(sig["top_score"])
            out_margin.append(sig["margin"])

    # Apply the pre-declared rule: 10th percentile of in_corpus distributions.
    top_score_min = round(percentile(in_top, PERCENTILE), 6)
    margin_min = round(percentile(in_margin, PERCENTILE), 6)

    # ---- transparency reporting (does NOT affect chosen thresholds) --------
    line = "=" * 74
    print(line)
    print("STAGE 3 — THRESHOLD CALIBRATION (calibration set only; GT untouched)")
    print(line)
    print(f"Calibration set sha256 : {calib['_meta']['content_sha256']}")
    print(f"in_corpus questions    : {len(in_top)}")
    print(f"out_of_corpus questions: {len(out_top)}")
    print(f"Rule                   : {PERCENTILE}th percentile of in_corpus")
    print("-" * 74)
    print("in_corpus  top_score :", describe(in_top))
    print("in_corpus  margin    :", describe(in_margin))
    print("out_corpus top_score :", describe(out_top))
    print("out_corpus margin    :", describe(out_margin))
    print("-" * 74)
    print(f"FROZEN TOP_SCORE_MIN = {top_score_min}")
    print(f"FROZEN MARGIN_MIN    = {margin_min}")

    # Transparency: how would the frozen rule classify the calibration set
    # itself? (Reported only; not used to adjust thresholds.)
    def abstains(t: float, m: float) -> bool:
        return (t < top_score_min) or (m < margin_min)

    in_correct = sum(
        1 for t, m in zip(in_top, in_margin) if not abstains(t, m)
    )
    out_correct = sum(
        1 for t, m in zip(out_top, out_margin) if abstains(t, m)
    )
    print("-" * 74)
    print("Calibration-set behaviour under frozen thresholds (transparency):")
    print(f"  in_corpus kept (not abstained)   : {in_correct}/{len(in_top)}")
    print(f"  out_corpus abstained (correct)   : {out_correct}/{len(out_top)}")
    print(line)

    write_thresholds_module(
        top_score_min=top_score_min,
        margin_min=margin_min,
        calib_hash=calib["_meta"]["content_sha256"],
        n_in=len(in_top),
        n_out=len(out_top),
    )
    print(f"Wrote frozen thresholds to: {THRESHOLDS_PATH}")


def write_thresholds_module(top_score_min: float, margin_min: float,
                            calib_hash: str, n_in: int, n_out: int) -> None:
    """Generate rag/thresholds.py as a frozen constant module with provenance."""
    content = f'''"""
rag/thresholds.py  — FROZEN Stage-3 abstention thresholds (AUTO-GENERATED)
==========================================================================

DO NOT hand-edit these values to chase better ground-truth scores. They were
produced by ``evaluation/calibration/calibrate_thresholds.py`` from the SEPARATE
synthetic calibration set, using a pre-declared rule fixed before the numbers
were seen:

    TOP_SCORE_MIN = {PERCENTILE}th percentile of in_corpus top_score
    MARGIN_MIN    = {PERCENTILE}th percentile of in_corpus margin

The 22 locked ground-truth cases were NOT used to select these values.

Provenance
----------
    calibration_set_sha256 : {calib_hash}
    in_corpus_questions    : {n_in}
    out_of_corpus_questions: {n_out}
    rule                   : {PERCENTILE}th percentile of the in_corpus distribution
    generated_on           : {date.today().isoformat()}

To re-calibrate (e.g. if the corpus changes), re-run:
    python evaluation/calibration/build_calibration_set.py
    python evaluation/calibration/calibrate_thresholds.py

Reminder: TOP_SCORE_MIN / MARGIN_MIN compare against cosine SIMILARITY, which is
a lexical/semantic similarity in [0, 1] — NOT a probability or confidence.
"""

# Minimum cosine similarity of the best retrieved chunk for the evidence to be
# considered strong enough to attempt an answer.
TOP_SCORE_MIN = {top_score_min}

# Minimum concentration margin (best score minus best score from a different
# source document) for the evidence to be considered focused enough.
MARGIN_MIN = {margin_min}

# Fixed abstention message (must match the ground-truth abstention wording).
ABSTAIN_MESSAGE = (
    "Insufficient evidence was found in the available procurement policies to "
    "answer this question reliably. Please verify with the relevant policy owner."
)

CALIBRATION_PROVENANCE = {{
    "calibration_set_sha256": "{calib_hash}",
    "rule": "{PERCENTILE}th percentile of in_corpus distribution",
    "in_corpus_questions": {n_in},
    "out_of_corpus_questions": {n_out},
    "top_score_min": {top_score_min},
    "margin_min": {margin_min},
    "generated_on": "{date.today().isoformat()}",
}}
'''
    with open(THRESHOLDS_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)


if __name__ == "__main__":
    main()
