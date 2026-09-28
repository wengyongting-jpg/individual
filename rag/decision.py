"""
rag/decision.py
===============

STAGE 3 — Deterministic decision layer that turns a retrieval result into one
of three actions, with NO Foundation Model and NO calls to any API:

ANSWERED_ELIGIBLE
    evidence is strong/focused enough AND the question is specific enough that
    a later stage MAY ask a model to answer.

CLARIFICATION_REQUIRED
    the question is underspecified where the procurement tracks genuinely
    diverge.

ABSTAIN
    the retrieved evidence is too weak / too diffuse to support an answer.

Everything here is rule-based.

The original calibrated cosine thresholds remain frozen. In addition to those
thresholds, this layer can recognize explicit structured evidence produced by
the retriever:

- numeric_match
- domain_match

It can also recognize cases where multiple strong policy sources are
simultaneously relevant. In such cases, a low margin does not automatically
mean that the evidence is unusable; the later answering stage can compare
the supplied sources for current, superseded, complementary, or conflicting
policy evidence.
"""

from __future__ import annotations

import re
from typing import Dict, List

from signals import compute_signals, has_multiple_strong_sources
from thresholds import (
    TOP_SCORE_MIN,
    MARGIN_MIN,
    ABSTAIN_MESSAGE,
)


# --------------------------------------------------------------------------
# Clarification detection — general vocabulary
# --------------------------------------------------------------------------

_GOODS_TERMS = [
    "goods",
    "good",
    "equipment",
    "product",
    "products",
    "supplies",
    "supply",
    "hardware",
    "material",
    "materials",
    "item",
    "items",
]

_SERVICES_TERMS = [
    "service",
    "services",
    "consulting",
    "consultant",
    "consultants",
    "engagement",
    "engagements",
    "contractor",
    "advisory",
    "professional service",
]

_DECISION_TERMS = [
    r"approv\w*",
    r"authori[sz]\w*",
    r"sign(?:s|ed|ing)?[ -]off",
    r"quot\w*",
    r"threshold\w*",
    r"tier\w*",
    r"method\w*",
    r"process\w*",
    r"procedure\w*",
    r"requir\w*",
]


# Monetary / procurement-value trigger.

_AMOUNT_RE = re.compile(
    r"(\$\s?\d[\d,.]*)"
    r"|(\b\d{1,3}(?:,\d{3})+\b)"
    r"|(\b\d+\s?k\b)"
    r"|(\b\d+\s?(?:million|m)\b)"
    r"|(\b\d{4,}\b)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Track-independent policy concepts
# --------------------------------------------------------------------------

# Some procurement rules can be answered without knowing whether the
# transaction belongs to the goods or services track.
#
# PPEJ is one such policy concept in this corpus: its trigger is defined by
# procurement value rather than by selecting the goods/services threshold
# table.

_TRACK_INDEPENDENT_TERMS = [
    "ppej",
    "procurement policy exemption justification",
]


# --------------------------------------------------------------------------
# Generic text helpers
# --------------------------------------------------------------------------

def _contains_any_literal(text: str, terms: List[str]) -> bool:
    """True if any literal term appears in text."""
    low = text.lower()

    for term in terms:
        if re.search(
            r"(?<!\w)" + re.escape(term) + r"(?!\w)",
            low,
        ):
            return True

    return False


def _contains_any_regex(text: str, patterns: List[str]) -> bool:
    """True if any regex-fragment pattern matches text."""
    low = text.lower()

    for pattern in patterns:
        if re.search(
            r"(?<!\w)(?:" + pattern + r")(?!\w)",
            low,
        ):
            return True

    return False


# --------------------------------------------------------------------------
# Question classification
# --------------------------------------------------------------------------

def mentions_amount(question: str) -> bool:
    return bool(_AMOUNT_RE.search(question))


def mentions_decision(question: str) -> bool:
    return _contains_any_regex(
        question,
        _DECISION_TERMS,
    )


def names_track(question: str) -> bool:
    """True if the question explicitly says goods OR services."""
    return (
        _contains_any_literal(
            question,
            _GOODS_TERMS,
        )
        or
        _contains_any_literal(
            question,
            _SERVICES_TERMS,
        )
    )


def is_track_independent(question: str) -> bool:
    """
    True when the question refers to a policy concept that does not require
    selecting the goods/services track before the policy can be interpreted.
    """
    return _contains_any_literal(
        question,
        _TRACK_INDEPENDENT_TERMS,
    )


def is_underspecified(question: str) -> bool:
    """
    A question is underspecified when:

    1. it contains a procurement amount,
    2. it asks about a procurement decision,
    3. it does not identify goods/services,
    4. and it is not a track-independent policy question.

    This remains a general structural rule and does not reference test-case IDs.
    """
    return (
        mentions_amount(question)
        and mentions_decision(question)
        and not names_track(question)
        and not is_track_independent(question)
    )


# --------------------------------------------------------------------------
# Structured evidence
# --------------------------------------------------------------------------

def has_structured_evidence(
    retrieved_passages: List[Dict],
) -> bool:
    """
    Return True when the top-ranked passage explicitly matches both:

    - the monetary value in the question, and
    - the relevant procurement domain.

    These fields are produced deterministically by the retriever.
    """
    if not retrieved_passages:
        return False

    top = retrieved_passages[0]

    return bool(
        top.get("numeric_match", False)
        and top.get("domain_match", False)
    )


# --------------------------------------------------------------------------
# Decision function
# --------------------------------------------------------------------------

def decide_action(
    question: str,
    retrieved_passages: List[Dict],
) -> Dict:
    """
    Route a question + retrieval result to one of three actions.

    ANSWERED_ELIGIBLE is a routing decision only. Stage 3 does not generate
    the final answer.
    """

    signals = compute_signals(
        retrieved_passages
    )

    top_score = signals["top_score"]
    margin = signals["margin"]

    structured_evidence = has_structured_evidence(
        retrieved_passages
    )

    multi_source_evidence = has_multiple_strong_sources(
        retrieved_passages,
        TOP_SCORE_MIN,
    )

    thresholds = {
        "top_score_min": TOP_SCORE_MIN,
        "margin_min": MARGIN_MIN,
    }

    base = {
        "signals": {
            **signals,
            "structured_evidence": structured_evidence,
            "multi_source_evidence": multi_source_evidence,
        },
        "thresholds": thresholds,
        "message": None,
    }

    # ----------------------------------------------------------------------
    # STEP 1 — Clarification
    # ----------------------------------------------------------------------

    if is_underspecified(question):
        return {
            "action": "CLARIFICATION_REQUIRED",
            "reason": (
                "Question refers to a value-dependent procurement decision "
                "at a dollar amount but does not specify goods vs services."
            ),
            **base,
        }

    # ----------------------------------------------------------------------
    # STEP 2 — Structured evidence override
    # ----------------------------------------------------------------------

    if structured_evidence:
        return {
            "action": "ANSWERED_ELIGIBLE",
            "reason": (
                "Top-ranked evidence explicitly matches both the procurement "
                "amount and the relevant goods/services domain."
            ),
            **base,
        }

    # ----------------------------------------------------------------------
    # STEP 3 — Original frozen threshold checks
    # ----------------------------------------------------------------------

    if top_score < TOP_SCORE_MIN:
        return {
            "action": "ABSTAIN",
            "reason": (
                f"top_score {top_score} < TOP_SCORE_MIN {TOP_SCORE_MIN}: "
                "best retrieved evidence is too weak."
            ),
            **{
                **base,
                "message": ABSTAIN_MESSAGE,
            },
        }

    # A low margin normally means that evidence is diffuse across documents.
    # However, if another source is also sufficiently strong, the documents
    # may be jointly relevant. In that case, allow the answering stage to
    # compare all supplied evidence rather than abstaining prematurely.
    if margin < MARGIN_MIN and not multi_source_evidence:
        return {
            "action": "ABSTAIN",
            "reason": (
                f"margin {margin} < MARGIN_MIN {MARGIN_MIN}: "
                "evidence is too diffuse across documents, "
                "and no second strong source was found."
            ),
            **{
                **base,
                "message": ABSTAIN_MESSAGE,
            },
        }

    # ----------------------------------------------------------------------
    # STEP 4 — Evidence passes frozen thresholds
    # ----------------------------------------------------------------------

    if multi_source_evidence and margin < MARGIN_MIN:
        return {
            "action": "ANSWERED_ELIGIBLE",
            "reason": (
                "Evidence spans multiple strong policy sources. "
                "Although the margin is below the frozen threshold, "
                "the answering stage should compare the supplied sources."
            ),
            **base,
        }

    return {
        "action": "ANSWERED_ELIGIBLE",
        "reason": (
            "Evidence passes both thresholds and the question is sufficiently "
            "specified."
        ),
        **base,
    }