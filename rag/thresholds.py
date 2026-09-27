"""
rag/thresholds.py  — FROZEN Stage-3 abstention thresholds (AUTO-GENERATED)
==========================================================================

DO NOT hand-edit these values to chase better ground-truth scores. They were
produced by ``evaluation/calibration/calibrate_thresholds.py`` from the SEPARATE
synthetic calibration set, using a pre-declared rule fixed before the numbers
were seen:

    TOP_SCORE_MIN = 10th percentile of in_corpus top_score
    MARGIN_MIN    = 10th percentile of in_corpus margin

The 22 locked ground-truth cases were NOT used to select these values.

Provenance
----------
    calibration_set_sha256 : 5a730ffc7bee78893f82243c042fbfea67c28aee029af5ef0345861d62f252f5
    in_corpus_questions    : 66
    out_of_corpus_questions: 24
    rule                   : 10th percentile of the in_corpus distribution
    generated_on           : 2026-09-25

To re-calibrate (e.g. if the corpus changes), re-run:
    python evaluation/calibration/build_calibration_set.py
    python evaluation/calibration/calibrate_thresholds.py

Reminder: TOP_SCORE_MIN / MARGIN_MIN compare against cosine SIMILARITY, which is
a lexical/semantic similarity in [0, 1] — NOT a probability or confidence.
"""

# Minimum cosine similarity of the best retrieved chunk for the evidence to be
# considered strong enough to attempt an answer.
TOP_SCORE_MIN = 0.238864

# Minimum concentration margin (best score minus best score from a different
# source document) for the evidence to be considered focused enough.
MARGIN_MIN = 0.030034

# Fixed abstention message (must match the ground-truth abstention wording).
ABSTAIN_MESSAGE = (
    "Insufficient evidence was found in the available procurement policies to "
    "answer this question reliably. Please verify with the relevant policy owner."
)

CALIBRATION_PROVENANCE = {
    "calibration_set_sha256": "5a730ffc7bee78893f82243c042fbfea67c28aee029af5ef0345861d62f252f5",
    "rule": "10th percentile of in_corpus distribution",
    "in_corpus_questions": 66,
    "out_of_corpus_questions": 24,
    "top_score_min": 0.238864,
    "margin_min": 0.030034,
    "generated_on": "2026-09-25",
}
