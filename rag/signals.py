"""
rag/signals.py
==============

STAGE 3 — Pure, dependency-free computation of the retrieval signals used by
BOTH the threshold calibrator and the decision layer. Keeping this in one place
guarantees calibration and runtime use the IDENTICAL signal definitions.

Signals (computed from a retriever's `retrieved_passages` list):

- top_score : the cosine similarity of the best-ranked chunk. Absolute
  strength of the single best piece of evidence.

- margin    : top_score minus the best score coming from a DIFFERENT source
  document than the top chunk. It measures how CONCENTRATED the evidence is
  in one policy document.

  A low margin can mean that evidence is diffuse across unrelated documents.
  However, a low margin can also occur when multiple policy documents are
  jointly relevant, such as current and superseded policy versions or
  complementary policy documents. The decision layer can use the additional
  multi-source signal to distinguish these cases.

- multi_source_evidence : True when at least one sufficiently strong passage
  comes from a different source document than the top-ranked passage.

Reminder: cosine similarity is a lexical/semantic similarity in [0, 1]. It is
NOT a probability or a calibrated confidence, and these signals must not be
described as such.
"""

from __future__ import annotations

from typing import Dict, List


def has_multiple_strong_sources(
    retrieved_passages: List[Dict],
    min_score: float,
) -> bool:
    """
    Return True when at least one sufficiently strong passage comes from a
    different source document than the top-ranked passage.

    This does not determine whether the sources agree, conflict, or represent
    current/superseded policy. It only identifies that multiple strong policy
    sources may need to be compared by the answering stage.
    """
    if not retrieved_passages:
        return False

    top_source = retrieved_passages[0]["source"]

    for passage in retrieved_passages[1:]:
        if (
            passage["source"] != top_source
            and float(passage["score"]) >= min_score
        ):
            return True

    return False


def compute_signals(
    retrieved_passages: List[Dict],
) -> Dict[str, float]:
    """
    Compute top_score and margin from a ranked passage list.

    ``retrieved_passages`` items must have keys ``source`` and ``score`` and
    be ordered best-first, as the retriever returns them.
    """
    if not retrieved_passages:
        return {
            "top_score": 0.0,
            "margin": 0.0,
        }

    top = retrieved_passages[0]
    top_score = float(top["score"])
    top_source = top["source"]

    # Best score from a source different to the top passage's source.
    other_source_best = None

    for passage in retrieved_passages[1:]:
        if passage["source"] != top_source:
            other_source_best = float(passage["score"])
            break

    if other_source_best is None:
        # No competing source in the retrieved set -> maximally concentrated.
        margin = top_score
    else:
        margin = top_score - other_source_best

    return {
        "top_score": round(top_score, 6),
        "margin": round(margin, 6),
    }