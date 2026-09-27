"""
evaluation/compare.py
====================

STAGE 7 — Fair baseline vs RAG comparison over the SAME 22 held-out cases, using
the SAME ground truth and scoring criteria. Produces
evaluation/results/comparison.json.

Three important honesty rules are enforced here:

  1. PRIMARY METRIC (revised per reviewer feedback on the Problem Statement):
     citation-grounded answer correctness on the fixed 22-case ground-truth
     set (evaluation/evaluate.py's primary_metric_citation_grounded_answer_
     correctness) is the project's core evaluation metric. Median response
     time is NOT the core metric: the corpus was written by this team, so the
     team cannot be the ones timing themselves reading it (they already know
     where every answer is), and a metric that only rewards speed also scores
     a fast WRONG answer highly.

  2. TASK COMPLETION TIME and SYSTEM LATENCY are both SECONDARY metrics, kept
     clearly separate from each other and from the primary metric above.
     Task-completion time is the time an INDEPENDENT reader — someone who did
     NOT write the 16 policy documents and has no prior familiarity with
     where each rule lives — takes to complete the policy-search task using
     each system. It is NOT the same as system compute latency. Neither has
     been measured yet: task-completion time needs an independent-tester
     study (framework below; must not be run by the document authors) and
     system latency is reported separately as a distinct, measured quantity.

  3. RAG answer-level metrics (rule accuracy, final answered-action accuracy)
     require a Foundation Model that has not been executed (no API key). Those
     are reported as PENDING EXECUTION, never fabricated. Only the deterministic
     and objective quantities are reported as measured.

Run:
    python evaluation/compare.py
"""

from __future__ import annotations

import json
import os
import statistics
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
RESULTS_DIR = os.path.join(HERE, "results")

BASELINE_PATH = os.path.join(RESULTS_DIR, "baseline_results.json")
RAG_RETRIEVAL_PATH = os.path.join(RESULTS_DIR, "rag_retrieval_results.json")
RAG_RESULTS_PATH = os.path.join(RESULTS_DIR, "rag_results.json")
EVAL_BASELINE_PATH = os.path.join(RESULTS_DIR, "evaluation_baseline.json")
EVAL_RAG_PATH = os.path.join(RESULTS_DIR, "evaluation_rag.json")
COMPARISON_PATH = os.path.join(RESULTS_DIR, "comparison.json")


def load(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def median_latency(results: List[Dict], key: str) -> float:
    vals = [r.get(key, 0.0) for r in results]
    return round(statistics.median(vals), 4) if vals else 0.0


def main() -> None:
    baseline = load(BASELINE_PATH)
    rag_ret = load(RAG_RETRIEVAL_PATH)
    rag_full = load(RAG_RESULTS_PATH)
    eval_baseline = load(EVAL_BASELINE_PATH)
    eval_rag = load(EVAL_RAG_PATH)

    baseline_lat = median_latency(baseline["results"], "latency_ms")
    rag_ret_lat = median_latency(rag_ret["results"], "latency_ms")

    comparison = {
        "_meta": {
            "stage": "Stage 7 — baseline vs RAG comparison",
            "same_corpus": "16 SynthCorp policy documents (incl. one superseded edition)",
            "same_ground_truth": "ground_truth.json (22 locked cases)",
            "same_criteria": "evaluation/evaluate.py",
            "model_execution": "PENDING EXECUTION (no API key; RAG answers not generated)",
        },

        # ---------------- PRIMARY METRIC (fixed test set) ----------------
        "primary_metric_citation_grounded_answer_correctness": {
            "status": eval_rag["primary_metric_citation_grounded_answer_correctness"]["status"],
            "definition": eval_rag["primary_metric_citation_grounded_answer_correctness"]["definition"],
            "total_answerable_cases":
                eval_rag["primary_metric_citation_grounded_answer_correctness"]["total_answerable_cases"],
            "scorable_now":
                eval_rag["primary_metric_citation_grounded_answer_correctness"]["scorable"],
            "correct":
                eval_rag["primary_metric_citation_grounded_answer_correctness"]["correct"],
            "accuracy_over_scorable":
                eval_rag["primary_metric_citation_grounded_answer_correctness"]["accuracy_over_scorable"],
            "pending":
                eval_rag["primary_metric_citation_grounded_answer_correctness"]["pending"],
            "why_pending": (
                "Requires the Foundation Model to actually run (no API key here) "
                "AND a human grader to mark each produced answer correct/incorrect "
                "against expected_answer (see "
                "evaluation/results/rule_accuracy_manual.json). Neither has "
                "happened yet, so nothing is scored as pass or fail."
            ),
            "baseline": "N/A (retrieval-only; produces no answer text to grade)",
        },

        # ---------------- SECONDARY METRIC: human task-completion time --------
        "secondary_metric_task_completion_time": {
            "status": "PENDING EXECUTION",
            "definition": (
                "Median wall-clock time for a procurement staff member to obtain "
                "a trustworthy answer to a policy question (read/search/verify), "
                "NOT system compute latency."
            ),
            "must_be_measured_by": (
                "Independent testers who did NOT author the 16 policy documents "
                "and have no prior familiarity with where each rule lives. The "
                "project team itself cannot run this study on their own timing, "
                "since they already know the corpus structure from having "
                "written it -- that would understate baseline search time for "
                "both systems and bias the comparison."
            ),
            "why_pending": (
                "Task-completion time requires an independent-tester study (timed "
                "trials answering the 22 questions with each system). No such "
                "study has been run, and system latency must NOT be presented as "
                "human task time."
            ),
            "measurement_framework": {
                "design": (
                    "Within-subjects timed trial: N participants, none of whom "
                    "wrote the policy corpus, each answer the 22 questions using "
                    "(a) manual keyword search over the 16 docs and (b) the RAG "
                    "assistant, order counterbalanced."
                ),
                "measure": "time from question shown to participant-confirmed answer",
                "primary_statistic": "median task-completion time per system",
                "target": (
                    "project target: reduce median task-completion time by >= 50% "
                    "vs the keyword-search baseline (to be tested, not assumed)"
                ),
            },
            "target_met": "PENDING EXECUTION",
        },

        # ---------------- TERTIARY/DIAGNOSTIC: SYSTEM LATENCY (measured) ------
        "tertiary_diagnostic_system_latency_ms_measured": {
            "note": (
                "Measured compute latency only, on this team's own machine. "
                "This is NOT the primary metric and NOT task-completion time -- "
                "it is a diagnostic figure only, reported for engineering "
                "context (see docs/cost_latency_tradeoff.md)."
            ),
            "baseline_keyword_retrieval_median": baseline_lat,
            "rag_retrieval_median": rag_ret_lat,
            "rag_end_to_end_median": "PENDING EXECUTION (includes model call; no API key)",
        },

        # ---------------- COMPONENT DETAIL (feeds the primary metric) --------
        "answer_correctness": {
            "baseline": "N/A (retrieval-only; produces no answer)",
            "rag": {
                "deterministic_action_accuracy_over_scorable":
                    eval_rag["action_correctness"]["accuracy_over_scorable"],
                "scorable_now": eval_rag["action_correctness"]["scorable"],
                "answered_cases_pending_model":
                    eval_rag["action_correctness"]["pending_model_execution"],
                "final_answer_correctness": "PENDING EXECUTION (no model)",
            },
        },
        "evidence_grounding": {
            "baseline_top1_hit_rate":
                eval_baseline["evidence_grounding"]["top1_source_hit_rate"],
            "baseline_top3_hit_rate":
                eval_baseline["evidence_grounding"]["top3_source_hit_rate"],
            "rag_grounding_hit_rate":
                eval_rag["evidence_grounding"]["hit_rate"],
            "note": (
                "Objective retrieval grounding (expected source retrieved). "
                "Comparable across systems. Baseline uses token-overlap ranking; "
                "RAG uses TF-IDF cosine over paragraph chunks."
            ),
        },
        "ambiguous_and_insufficient_handling": {
            "baseline": (
                "Cannot abstain or ask for clarification — always returns "
                "passages (5/5 insufficient cases return near-misses)."
            ),
            "rag": {
                "ambiguous_clarification_correct":
                    eval_rag["missing_ambiguous_handling"]["ambiguous"],
                "insufficient_abstain": (
                    eval_rag["missing_ambiguous_handling"]["insufficient_evidence"]
                ),
                "note": (
                    "RAG's deterministic decision layer can clarify/abstain; "
                    "these actions are measured now and independent of the model."
                ),
            },
        },
        "rule_accuracy": {
            "baseline": "N/A (no answer text)",
            "rag": eval_rag["rule_accuracy"]["status"],
        },
        "api_token_cost": {
            "baseline": "$0 (no API, standard library only)",
            "rag": "PENDING EXECUTION (depends on model + tokens; not executed)",
        },

        "summary": {
            "what_is_measured_now": [
                "system retrieval latency (both systems) — diagnostic only",
                "objective evidence grounding (both systems)",
                "RAG deterministic clarify/abstain action accuracy",
            ],
            "what_is_pending_execution": [
                "PRIMARY: citation-grounded answer correctness on the fixed "
                "22-case set (needs model + human grading)",
                "independent-tester task-completion time (secondary metric)",
                "RAG end-to-end latency (needs model)",
                "API token cost (needs model)",
            ],
            "headline": (
                "RAG adds a clarify/abstain capability the baseline "
                "structurally lacks, and the corpus now contains a genuine "
                "superseded-policy case and a genuine cross-document "
                "contradiction (TC21/TC22) that the baseline cannot flag at "
                "all. The PRIMARY metric — citation-grounded answer "
                "correctness — remains PENDING until a model is executed and "
                "its answers are graded; task-completion time remains PENDING "
                "until independent (non-author) testers run the timed study."
            ),
        },
    }

    with open(COMPARISON_PATH, "w", encoding="utf-8") as fh:
        json.dump(comparison, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print("Wrote comparison to:", COMPARISON_PATH)
    print("PRIMARY metric (citation-grounded answer correctness): PENDING EXECUTION")
    print("Secondary metric (independent-tester task time)      : PENDING EXECUTION")
    print("Tertiary/diagnostic — baseline retrieval median latency:", baseline_lat, "ms")
    print("Tertiary/diagnostic — RAG retrieval median latency     :", rag_ret_lat, "ms")


if __name__ == "__main__":
    main()
