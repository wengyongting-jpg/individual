"""
rag/test_decision.py
====================

STAGE 3 — Manual inspection of the decision layer on REPRESENTATIVE, hand-written
questions (NOT the ground-truth cases and NOT the calibration set). Purpose is to
eyeball that clarification / abstention / answer-eligible routing behaves sensibly.

Nothing here reads ground_truth.json.

Run:
    python rag/test_decision.py
"""

from __future__ import annotations

from rag_pipeline import RagPipeline

# (expectation_hint, question) — the hint is just for the reader; the system is
# not scored here.
SAMPLES = [
    ("answer-eligible (specific, in corpus)",
     "What is the procurement card per-transaction limit?"),
    ("answer-eligible (names services)",
     "Who approves a $50,000 consulting engagement?"),
    ("clarification (amount + decision, no goods/services)",
     "Who signs off on a $50,000 purchase?"),
    ("clarification (quotes at an amount, track unspecified)",
     "How many quotes are needed for an $80,000 purchase?"),
    ("abstain (topic absent from corpus)",
     "What is the policy on employee travel reimbursement rates?"),
    ("abstain (absent topic, plausible)",
     "What warranty must suppliers provide on delivered goods?"),
]


def main() -> None:
    pipe = RagPipeline()
    for hint, q in SAMPLES:
        out = pipe.run(q)
        print("=" * 80)
        print(f"QUESTION      : {q}")
        print(f"READER HINT   : {hint}")
        print(f"ACTION        : {out['action']}")
        print(f"SIGNALS       : {out['signals']}  thresholds={out['thresholds']}")
        print(f"REASON        : {out['reason']}")
        print(f"TOP SOURCE    : {out['top_source']}")
        if out["abstain_message"]:
            print(f"ABSTAIN MSG   : {out['abstain_message']}")
        print()


if __name__ == "__main__":
    main()
