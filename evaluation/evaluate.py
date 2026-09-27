"""
evaluation/evaluate.py
=====================

STAGE 6 — Common evaluation harness. Scores a system's saved results against the
LOCKED ground truth using the SAME criteria for baseline and RAG.

>>> PRIMARY METRIC (revised per reviewer feedback on the Problem Statement) <<<
citation_grounded_answer_correctness is the PRIMARY evaluation metric on the
fixed 22-case ground-truth set: for every case where a substantive answer is
expected (expected_action == "ANSWERED"), the case counts as correct ONLY if
the system (a) actually answered (not abstained/clarified), (b) the answer
text matches the expected answer (rule_accuracy), AND (c) an expected source
was cited (evidence_grounding). All three must hold — a fast, uncited, or
wrong answer does not count, precisely because a metric that only rewards
speed can score a fast WRONG answer highly. System latency (median response
time) is NOT the core metric and is reported only as a secondary, diagnostic
quantity (see evaluation/compare.py and docs/cost_latency_tradeoff.md) — it
measures compute time, not whether staff actually complete their task faster,
and it must never be measured by the people who wrote the underlying policy
documents (see the note in evaluation/compare.py).

Scored dimensions (using the existing ground-truth definitions, not a new
scoring scheme):

  0. citation_grounded_answer_correctness   PRIMARY METRIC — see above.
  1. action_correctness   predicted_action == expected_action
                          (ANSWERED / CLARIFICATION_REQUIRED / ABSTAIN)
  2. missing_ambiguous_handling
                          same as action correctness on the ambiguous +
                          insufficient_evidence categories (does the system
                          correctly choose CLARIFICATION_REQUIRED / ABSTAIN?)
  3. evidence_grounding   for cases the system answered, does the retrieved
                          evidence actually include an expected source?
                          (objective; only where expected_source is non-empty)
  4. rule_accuracy        does the produced answer match the expected answer?
                          This requires generated answer text. When the model
                          did not run (PENDING_EXECUTION), this is recorded as
                          PENDING — never scored as pass/fail, never fabricated.

Usage:
    python evaluation/evaluate.py --system baseline
    python evaluation/evaluate.py --system rag
    python evaluation/evaluate.py --results evaluation/results/rag_results.json

The baseline is retrieval-only (no action decision), so for the baseline we
evaluate ONLY the objective retrieval-grounding dimension and clearly record
that action/rule dimensions are not applicable to a non-LLM retrieval baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections import defaultdict
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
RESULTS_DIR = os.path.join(HERE, "results")
GROUND_TRUTH_PATH = os.path.join(REPO_ROOT, "ground_truth.json")

SYSTEM_FILES = {
    "baseline": os.path.join(RESULTS_DIR, "baseline_results.json"),
    "rag": os.path.join(RESULTS_DIR, "rag_results.json"),
}

# Actions that mean "the system produced a substantive answer".
ANSWERED = "ANSWERED"
MODEL_NOT_RUN = {"PENDING_EXECUTION", "MODEL_ERROR", "MODEL_OUTPUT_INVALID"}


def load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_ground_truth() -> Dict:
    return load_json(GROUND_TRUTH_PATH)


def _gt_by_id(gt: Dict) -> Dict[str, Dict]:
    return {c["test_case_id"]: c for c in gt["test_cases"]}


# Rule accuracy compares FREE-TEXT model answers against expected_answer.
# Automated string-similarity matching is deliberately NOT used to decide
# pass/fail here: a heuristic that "mostly" matches wording is exactly the
# kind of silent-fabrication risk this project's evaluation avoids elsewhere
# (see PENDING_EXECUTION handling throughout). Instead, once the model has
# actually run, a human grader marks each ANSWERED case correct/incorrect
# against expected_answer and records it in this OPTIONAL annotation file:
#   evaluation/results/rule_accuracy_manual.json
#   {"TC01": true, "TC02": false, ...}
# If the file is absent (the current state — no model has run), every case
# is PENDING here, exactly as before this change.
RULE_ACCURACY_MANUAL_PATH = os.path.join(RESULTS_DIR, "rule_accuracy_manual.json")


def _load_rule_accuracy_annotations() -> Dict[str, bool]:
    if not os.path.exists(RULE_ACCURACY_MANUAL_PATH):
        return {}
    return load_json(RULE_ACCURACY_MANUAL_PATH)


def evaluate_rag(results: List[Dict], gt_by_id: Dict[str, Dict]) -> Dict:
    total = len(results)
    action_correct = 0
    action_scorable = 0            # cases where the action is known (model ran or deterministic)
    action_pending = 0

    grounding_scorable = 0
    grounding_hits = 0

    rule_pending = 0
    rule_scorable = 0
    rule_correct = 0
    rule_note = []

    rule_annotations = _load_rule_accuracy_annotations()

    # PRIMARY METRIC accumulators (see module docstring).
    primary_total = 0       # cases where expected_action == "ANSWERED"
    primary_scorable = 0    # of those, cases where all 3 components are known
    primary_correct = 0     # of those, cases where all 3 components passed
    primary_pending = 0

    by_cat = defaultdict(lambda: {"correct": 0, "total": 0, "pending": 0})

    for r in results:
        tc = gt_by_id[r["test_case_id"]]
        expected_action = tc["expected_action"]
        predicted_action = r["predicted_action"]
        cat = r["category"]
        by_cat[cat]["total"] += 1
        this_case_grounded = None   # None = not applicable/unknown
        this_case_rule_ok = None

        # 1 & 2: action correctness.
        if predicted_action in MODEL_NOT_RUN:
            # The system's terminal action is unknown because the model step is
            # pending. We do NOT guess it.
            action_pending += 1
            by_cat[cat]["pending"] += 1
        else:
            action_scorable += 1
            if predicted_action == expected_action:
                action_correct += 1
                by_cat[cat]["correct"] += 1

        # 3: evidence grounding — objective, only where an expected source exists.
        expected_source = tc.get("expected_source", [])
        if expected_source:
            grounding_scorable += 1
            retrieved_sources = {e.get("source") for e in r.get("evidence", [])}
            # fall back to citations if evidence empty
            retrieved_sources |= set(r.get("citations", []))
            this_case_grounded = any(s in expected_source for s in retrieved_sources)
            if this_case_grounded:
                grounding_hits += 1

        # 4: rule accuracy — needs a MODEL-GENERATED ANSWERED answer to compare
        # against the expected answer text. Only applicable when:
        #   * the case is answerable in GT (expected_answer is not None), AND
        #   * the system actually produced an ANSWERED answer via the model.
        # A deterministic ABSTAIN/CLARIFICATION on an answerable case is a wrong
        # ACTION (already captured above); its fixed message must NOT be
        # compared to the expected policy answer, so it is not rule-scorable.
        if tc["expected_answer"] is not None:
            if predicted_action == ANSWERED and r.get("answer"):
                rule_scorable += 1  # a real answer exists -> gradeable
                if r["test_case_id"] in rule_annotations:
                    this_case_rule_ok = bool(rule_annotations[r["test_case_id"]])
                    if this_case_rule_ok:
                        rule_correct += 1
                # else: answer exists but has not yet been human-graded —
                # this_case_rule_ok stays None (not scored as pass or fail).
            elif r.get("model_status") in MODEL_NOT_RUN:
                rule_pending += 1
            # else: system chose ABSTAIN/CLARIFICATION on an answerable case ->
            # not rule-scorable (counted as an action error, not a rule error).

        # 0: PRIMARY METRIC — citation-grounded answer correctness. Only
        # defined for cases where a substantive answer is expected at all.
        if expected_action == ANSWERED:
            primary_total += 1
            if this_case_grounded is None or this_case_rule_ok is None or predicted_action in MODEL_NOT_RUN:
                primary_pending += 1
            else:
                primary_scorable += 1
                if predicted_action == ANSWERED and this_case_grounded and this_case_rule_ok:
                    primary_correct += 1

    if rule_scorable == 0 and rule_pending > 0:
        rule_note.append(
            "Rule accuracy is PENDING: the Foundation Model did not run "
            "(no API key), so no answer text exists to compare against "
            "expected_answer. Not scored, not fabricated."
        )
    elif rule_scorable and not rule_annotations:
        rule_note.append(
            "Answer text now exists but has not been human-graded against "
            "expected_answer yet — see evaluation/results/rule_accuracy_manual.json. "
            "Not scored, not fabricated."
        )

    def rate(n, d):
        return round(n / d, 4) if d else None

    return {
        "system": "rag",
        "total_cases": total,
        "primary_metric_citation_grounded_answer_correctness": {
            "definition": (
                "For every case where a substantive answer is expected "
                "(expected_action == 'ANSWERED'): correct iff the system "
                "answered (not abstain/clarify) AND cited an expected "
                "source AND a human grader marked the answer text correct "
                "against expected_answer. This is the PRIMARY metric on the "
                "fixed ground-truth set, per reviewer feedback — median "
                "response time is not used as a core metric."
            ),
            "total_answerable_cases": primary_total,
            "scorable": primary_scorable,
            "correct": primary_correct,
            "accuracy_over_scorable": rate(primary_correct, primary_scorable),
            "pending": primary_pending,
            "status": "PENDING_EXECUTION" if primary_pending and not primary_scorable else "PARTIAL/OK",
        },
        "action_correctness": {
            "scorable": action_scorable,
            "correct": action_correct,
            "accuracy_over_scorable": rate(action_correct, action_scorable),
            "pending_model_execution": action_pending,
            "note": (
                "Deterministic ABSTAIN/CLARIFICATION_REQUIRED actions are "
                "scorable now. ANSWERED_ELIGIBLE cases are PENDING until the "
                "model runs. This is a SECONDARY/component metric — see "
                "primary_metric_citation_grounded_answer_correctness above."
            ),
        },
        "missing_ambiguous_handling": {
            "ambiguous": dict(by_cat["ambiguous"]),
            "insufficient_evidence": dict(by_cat["insufficient_evidence"]),
        },
        "evidence_grounding": {
            "scorable": grounding_scorable,
            "hits": grounding_hits,
            "hit_rate": rate(grounding_hits, grounding_scorable),
            "note": "Objective: expected source present in retrieved evidence.",
        },
        "rule_accuracy": {
            "scorable": rule_scorable,
            "correct": rule_correct,
            "pending": rule_pending,
            "status": "PENDING_EXECUTION" if rule_pending and not rule_scorable else "PARTIAL/OK",
            "note": " ".join(rule_note) or "Compared answer text vs expected_answer (human-graded).",
        },
        "per_category_action": {k: dict(v) for k, v in by_cat.items()},
    }


def evaluate_baseline(results: List[Dict], gt_by_id: Dict[str, Dict]) -> Dict:
    """The keyword baseline is retrieval-only: score ONLY objective grounding."""
    grounding_scorable = 0
    top1_hits = 0
    top3_hits = 0
    for r in results:
        tc = gt_by_id[r["test_case_id"]]
        expected_source = tc.get("expected_source", [])
        if not expected_source:
            continue
        grounding_scorable += 1
        if r.get("top_source") in expected_source:
            top1_hits += 1
        if any(s in expected_source for s in r.get("retrieved_sources", [])):
            top3_hits += 1

    def rate(n, d):
        return round(n / d, 4) if d else None

    return {
        "system": "baseline",
        "total_cases": len(results),
        "note": (
            "Keyword baseline is retrieval-only (no LLM), so it produces no "
            "ANSWERED/CLARIFICATION/ABSTAIN action and no answer text. Only "
            "objective retrieval grounding is applicable."
        ),
        "evidence_grounding": {
            "scorable": grounding_scorable,
            "top1_source_hit_rate": rate(top1_hits, grounding_scorable),
            "top3_source_hit_rate": rate(top3_hits, grounding_scorable),
        },
        "action_correctness": "N/A (no decision layer in the baseline)",
        "rule_accuracy": "N/A (baseline generates no answer text)",
    }


def evaluate_file(path: str, system_hint: Optional[str] = None) -> Dict:
    payload = load_json(path)
    results = payload["results"]
    gt_by_id = _gt_by_id(load_ground_truth())

    system = system_hint or payload.get("_meta", {}).get("system", "")
    if "baseline" in system:
        return evaluate_baseline(results, gt_by_id)
    return evaluate_rag(results, gt_by_id)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=list(SYSTEM_FILES), help="baseline or rag")
    ap.add_argument("--results", help="explicit path to a results json")
    args = ap.parse_args()

    if args.results:
        path = args.results
        hint = None
    elif args.system:
        path = SYSTEM_FILES[args.system]
        hint = args.system
    else:
        ap.error("Provide --system {baseline,rag} or --results PATH")

    report = evaluate_file(path, hint)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Save alongside the results.
    out_path = os.path.join(RESULTS_DIR, f"evaluation_{report['system']}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nSaved evaluation to: {out_path}")


if __name__ == "__main__":
    main()
