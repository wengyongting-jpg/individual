"""
rag/rag_answer.py
==================

STAGE 4/5/6 — Final RAG answer pipeline.

Full flow:

question
   |
retrieve top-k passages           [retriever.py]
   |
decide_action()                   [decision.py]
   |
+--------------------------------------------------------------+
| action == ABSTAIN                -> fixed message             |
| action == CLARIFICATION_REQUIRED -> clarifying prompt         |
| action == ANSWERED_ELIGIBLE     -> Foundation Model           |
|                                     -> structured JSON         |
|                                     -> Stage 6 validation      |
|                                     -> one-time regeneration   |
+--------------------------------------------------------------+

Key properties:

- ABSTAIN and CLARIFICATION_REQUIRED are resolved WITHOUT model call.
- Foundation Model is called ONLY for ANSWERED_ELIGIBLE cases.
- Model output is validated structurally.
- Stage 6 performs deterministic policy-answer validation.
- If Stage 6 fails, the system allows ONE constrained regeneration.
- The regenerated answer is validated again.
- No more than one regeneration is attempted.
- The system never fabricates an answer when the API key is unavailable.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from retriever import build_retriever, DEFAULT_TOP_K, Retriever
from decision import decide_action
from thresholds import ABSTAIN_MESSAGE
from prompt import (
    build_messages,
    parse_and_validate,
    OutputValidationError,
)
from model_client import ModelClient


def validate_policy_answer(
    question: str,
    answer: str,
    evidence: List[Dict],
    citations: List[str],
    confidence: str,
) -> Dict:
    """
    STAGE 6 — Deterministic policy-answer validation.

    This validator checks whether a generated answer properly handles
    current/superseded policy relationships present in the evidence.

    It does NOT generate policy content.
    It only detects missing mandatory disclosures.
    """

    answer_lower = str(answer).lower()

    # ---------------------------------------------------------------
    # Collect evidence sources
    # ---------------------------------------------------------------
    sources = {
        e.get("source", "")
        for e in evidence
        if isinstance(e, dict) and e.get("source")
    }

    superseded_sources = []
    current_sources = []

    for e in evidence:
        if not isinstance(e, dict):
            continue

        source = e.get("source", "")
        text = str(e.get("text", "")).lower()

        if any(
            marker in text
            for marker in [
                "superseded",
                "no longer in effect",
                "outdated",
                "historical",
                "archived",
                "no longer effective",
            ]
        ):
            superseded_sources.append(source)
        else:
            current_sources.append(source)

    issues = []

    # ---------------------------------------------------------------
    # Current + superseded policy relationship
    # ---------------------------------------------------------------
    if superseded_sources and current_sources:

        superseded_disclosed = any(
            phrase in answer_lower
            for phrase in [
                "superseded",
                "no longer in effect",
                "outdated",
                "historical",
                "archived",
                "no longer effective",
            ]
        )

        must_not_use_disclosed = any(
            phrase in answer_lower
            for phrase in [
                "must not be used",
                "should not be used",
                "do not use",
                "not be used for current",
                "cannot be used for current",
            ]
        )

        if not superseded_disclosed:
            issues.append(
                "Relevant superseded policy is present in the evidence, "
                "but its superseded status is not disclosed in the answer."
            )

        if not must_not_use_disclosed:
            issues.append(
                "The answer does not explicitly state that the superseded "
                "policy must not be used for current decisions."
            )

        if confidence == "high":
            issues.append(
                "Confidence is 'high' even though the answer contains "
                "current and superseded policy evidence."
            )

    # ---------------------------------------------------------------
    # Citation coverage
    # ---------------------------------------------------------------
    missing_citations = sources - set(citations)

    if missing_citations:
        issues.append(
            "Material evidence sources are missing from citations: "
            + ", ".join(sorted(missing_citations))
        )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "superseded_sources": sorted(set(superseded_sources)),
        "current_sources": sorted(set(current_sources)),
    }


class RagAnswerPipeline:
    """
    End-to-end RAG:
    retrieval + deterministic decision + model generation
    + deterministic validation + optional one-time regeneration.
    """

    def __init__(
        self,
        top_k: int = DEFAULT_TOP_K,
        retriever: Optional[Retriever] = None,
        model_client: Optional[ModelClient] = None,
    ):
        self.top_k = top_k

        self.retriever = (
            retriever
            if retriever is not None
            else build_retriever()
        )

        self.model_client = (
            model_client
            if model_client is not None
            else ModelClient()
        )

    def answer(
        self,
        question: str,
        top_k: int = None,
    ) -> Dict:

        # ===========================================================
        # STAGE 1/2 — Retrieval
        # ===========================================================
        k = top_k if top_k is not None else self.top_k

        retrieval = self.retriever.retrieve(
            question,
            top_k=k,
        )

        passages = retrieval["retrieved_passages"]

        # ===========================================================
        # STAGE 3 — Deterministic decision
        # ===========================================================
        decision = decide_action(
            question,
            passages,
        )

        action = decision["action"]

        base = {
            "question": question,
            "retrieval_method": retrieval["retrieval_method"],
            "retrieved_passages": passages,
            "top_source": (
                passages[0]["source"]
                if passages
                else None
            ),
            "signals": decision["signals"],
            "thresholds": decision["thresholds"],
            "retrieval_latency_ms": retrieval["latency_ms"],
            "decision_reason": decision["reason"],
        }

        # ===========================================================
        # ABSTAIN
        # ===========================================================
        if action == "ABSTAIN":

            return {
                **base,
                "action": "ABSTAIN",
                "answer": ABSTAIN_MESSAGE,
                "evidence": [],
                "citations": [],
                "confidence": "n/a",
                "model_status": "NOT_CALLED",
                "model_latency_ms": 0.0,
                "model_usage": {},
            }

        # ===========================================================
        # CLARIFICATION REQUIRED
        # ===========================================================
        if action == "CLARIFICATION_REQUIRED":

            clarifying = (
                "This question does not specify whether the purchase is "
                "for GOODS or SERVICES, and the applicable rule differs "
                "between the two. Could you confirm which type of purchase "
                "this is?"
            )

            return {
                **base,
                "action": "CLARIFICATION_REQUIRED",
                "answer": clarifying,
                "evidence": [
                    {
                        "source": p["source"],
                        "text": p["text"],
                    }
                    for p in passages
                ],
                "citations": sorted(
                    {
                        p["source"]
                        for p in passages
                    }
                ),
                "confidence": "n/a",
                "model_status": "NOT_CALLED",
                "model_latency_ms": 0.0,
                "model_usage": {},
            }

        # ===========================================================
        # ANSWERED_ELIGIBLE -> Foundation Model
        # ===========================================================
        evidence_for_model = [
            {
                "source": p["source"],
                "text": p["text"],
            }
            for p in passages
        ]

        messages = build_messages(
            question,
            evidence_for_model,
        )

        model_res = self.model_client.complete(messages)

        # ===========================================================
        # API KEY NOT AVAILABLE
        # ===========================================================
        if model_res.status == "PENDING_EXECUTION":

            return {
                **base,
                "action": "PENDING_EXECUTION",
                "answer": None,
                "evidence": evidence_for_model,
                "citations": sorted(
                    {
                        p["source"]
                        for p in evidence_for_model
                    }
                ),
                "confidence": "n/a",
                "model_status": "PENDING_EXECUTION",
                "model_note": model_res.error,
                "model_config": model_res.config,
                "model_latency_ms": 0.0,
                "model_usage": {},
            }

        # ===========================================================
        # MODEL ERROR
        # ===========================================================
        if model_res.status == "ERROR":

            return {
                **base,
                "action": "MODEL_ERROR",
                "answer": None,
                "evidence": evidence_for_model,
                "citations": sorted(
                    {
                        p["source"]
                        for p in evidence_for_model
                    }
                ),
                "confidence": "n/a",
                "model_status": "ERROR",
                "model_note": model_res.error,
                "model_latency_ms": model_res.latency_ms,
                "model_usage": {},
            }

        # ===========================================================
        # STRUCTURED OUTPUT VALIDATION
        # ===========================================================
        try:

            parsed = parse_and_validate(
                model_res.raw_text
            )

        except OutputValidationError as e:

            return {
                **base,
                "action": "MODEL_OUTPUT_INVALID",
                "answer": None,
                "raw_model_text": model_res.raw_text,
                "evidence": evidence_for_model,
                "citations": sorted(
                    {
                        p["source"]
                        for p in evidence_for_model
                    }
                ),
                "confidence": "n/a",
                "model_status": "OK_BUT_INVALID",
                "model_note": str(e),
                "model_latency_ms": model_res.latency_ms,
                "model_usage": model_res.usage,
            }

        # ===========================================================
        # STAGE 6 — Initial deterministic validation
        # ===========================================================
        validation = validate_policy_answer(
            question=question,
            answer=parsed["answer"],
            evidence=parsed["evidence"],
            citations=parsed["citations"],
            confidence=parsed["confidence"],
        )

        # ===========================================================
        # INITIAL OUTPUT PASSED
        # ===========================================================
        if validation["valid"]:

            return {
                **base,
                "action": parsed["action"],
                "answer": parsed["answer"],
                "evidence": parsed["evidence"],
                "citations": parsed["citations"],
                "confidence": parsed["confidence"],
                "model_status": "OK",
                "model_validation": validation,
                "regeneration_used": False,
                "model_latency_ms": model_res.latency_ms,
                "model_usage": model_res.usage,
            }

        # ===========================================================
        # STAGE 6B — ONE-TIME REGENERATION
        # ===========================================================
        regeneration_prompt = """
The previous answer failed a deterministic policy-completeness check.

Regenerate the answer using ONLY the supplied evidence.

Do not invent, infer, or add policy information that is not supported
by the evidence.

Correct EVERY validation issue listed below.

Validation issues:
{issues}

Additional requirements:

1. State the CURRENT applicable policy clearly.
2. If a supplied source is explicitly superseded, historical, outdated,
   or no longer in effect, explicitly state that.
3. If the evidence supports it, explicitly state that the superseded
   policy must not be used for current decisions.
4. Include every materially relevant source in the citations.
5. Do not assume that the first or highest-scoring retrieved source
   is the current policy.
6. Keep the answer concise but complete.
7. Return exactly the same required JSON structure.
""".format(
            issues="\n".join(
                f"- {issue}"
                for issue in validation["issues"]
            )
        )

        regeneration_messages = build_messages(
            question,
            evidence_for_model,
        )

        regeneration_messages.append(
            {
                "role": "user",
                "content": regeneration_prompt,
            }
        )

        regeneration_res = self.model_client.complete(
            regeneration_messages
        )

        # ===========================================================
        # REGENERATION FAILED
        # ===========================================================
        if regeneration_res.status != "OK":

            return {
                **base,
                "action": parsed["action"],
                "answer": parsed["answer"],
                "evidence": parsed["evidence"],
                "citations": parsed["citations"],
                "confidence": parsed["confidence"],
                "model_status": "OK_VALIDATION_FAILED",
                "model_validation": validation,
                "regeneration_used": True,
                "regeneration_note": (
                    "Initial output failed Stage 6 validation, "
                    "but regeneration could not be completed."
                ),
                "model_latency_ms": (
                    model_res.latency_ms
                    + regeneration_res.latency_ms
                ),
                "model_usage": {
                    "initial": model_res.usage,
                    "regeneration": regeneration_res.usage,
                },
            }

        # ===========================================================
        # VALIDATE REGENERATED STRUCTURED OUTPUT
        # ===========================================================
        try:

            regenerated = parse_and_validate(
                regeneration_res.raw_text
            )

        except OutputValidationError as e:

            return {
                **base,
                "action": parsed["action"],
                "answer": parsed["answer"],
                "evidence": parsed["evidence"],
                "citations": parsed["citations"],
                "confidence": parsed["confidence"],
                "model_status": "OK_VALIDATION_FAILED",
                "model_validation": validation,
                "regeneration_used": True,
                "regeneration_note": (
                    "Initial output failed Stage 6 validation and "
                    "regeneration returned invalid structured output."
                ),
                "regeneration_error": str(e),
                "model_latency_ms": (
                    model_res.latency_ms
                    + regeneration_res.latency_ms
                ),
                "model_usage": {
                    "initial": model_res.usage,
                    "regeneration": regeneration_res.usage,
                },
            }

        # ===========================================================
        # STAGE 6C — VALIDATE REGENERATED ANSWER
        # ===========================================================
        regeneration_validation = validate_policy_answer(
            question=question,
            answer=regenerated["answer"],
            evidence=regenerated["evidence"],
            citations=regenerated["citations"],
            confidence=regenerated["confidence"],
        )

        # ===========================================================
        # REGENERATION PASSED
        # ===========================================================
        if regeneration_validation["valid"]:

            return {
                **base,
                "action": regenerated["action"],
                "answer": regenerated["answer"],
                "evidence": regenerated["evidence"],
                "citations": regenerated["citations"],
                "confidence": regenerated["confidence"],
                "model_status": "OK_REGENERATED",
                "model_validation": regeneration_validation,
                "initial_validation": validation,
                "regeneration_used": True,
                "regeneration_note": (
                    "Initial model output failed Stage 6 validation "
                    "and was successfully regenerated."
                ),
                "model_latency_ms": (
                    model_res.latency_ms
                    + regeneration_res.latency_ms
                ),
                "model_usage": {
                    "initial": model_res.usage,
                    "regeneration": regeneration_res.usage,
                },
            }

        # ===========================================================
        # REGENERATION ALSO FAILED
        # ===========================================================
        return {
            **base,
            "action": regenerated["action"],
            "answer": regenerated["answer"],
            "evidence": regenerated["evidence"],
            "citations": regenerated["citations"],
            "confidence": regenerated["confidence"],
            "model_status": "OK_REGENERATION_VALIDATION_FAILED",
            "model_validation": regeneration_validation,
            "initial_validation": validation,
            "regeneration_used": True,
            "regeneration_note": (
                "Initial output failed Stage 6 validation and the "
                "one-time regeneration also failed validation."
            ),
            "model_latency_ms": (
                model_res.latency_ms
                + regeneration_res.latency_ms
            ),
            "model_usage": {
                "initial": model_res.usage,
                "regeneration": regeneration_res.usage,
            },
        }


# ===================================================================
# DIRECT TEST
# ===================================================================

if __name__ == "__main__":

    pipe = RagAnswerPipeline()

    for q in [
        "What is the procurement card per-transaction limit?",
        "Who signs off on a $50,000 purchase?",
        "What is the policy on employee travel reimbursement?",
        "What is the Ontario supplier preference under the provincial trade policy?",
    ]:

        out = pipe.answer(q)

        print("=" * 80)
        print("Q:", q)
        print("action        :", out["action"])
        print("model_status  :", out["model_status"])
        print("answer        :", out["answer"])
        print("citations     :", out["citations"])

        if "model_validation" in out:
            print(
                "validation    :",
                out["model_validation"],
            )

        if "initial_validation" in out:
            print(
                "initial_validation :",
                out["initial_validation"],
            )

        if "regeneration_used" in out:
            print(
                "regeneration_used :",
                out["regeneration_used"],
            )

        if "regeneration_note" in out:
            print(
                "regeneration_note :",
                out["regeneration_note"],
            )