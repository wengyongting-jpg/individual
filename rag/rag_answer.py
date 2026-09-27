"""
rag/rag_answer.py
=================

STAGE 4/5 — Final RAG answer pipeline (grounded answer generation).

Full flow:

    question
       |
    retrieve top-k passages           [retriever.py]
       |
    decide_action()                   [decision.py]  (deterministic)
       |
    +--------------------------------------------------------------+
    | action == ABSTAIN                -> return fixed message      |
    | action == CLARIFICATION_REQUIRED -> return clarifying prompt  |
    | action == ANSWERED_ELIGIBLE      -> call Foundation Model     |
    |                                     with prompt + evidence,   |
    |                                     validate structured JSON  |
    +--------------------------------------------------------------+

Key properties:
  * ABSTAIN and CLARIFICATION_REQUIRED are resolved WITHOUT any model call —
    they are deterministic (Stage 3). This guarantees the system never asks the
    model to answer a case it already decided to abstain/clarify on.
  * The model is called ONLY for ANSWERED_ELIGIBLE cases AND only when an API
    key is configured. With no key, that case is returned as PENDING_EXECUTION
    (never fabricated).
  * The model's structured reply is validated (rag/prompt.py). If the model
    returns ABSTAIN/CLARIFICATION_REQUIRED even after the deterministic layer
    allowed an answer, we RESPECT the model's more cautious choice (it is a
    second line of defence and may see that the evidence is insufficient).

The returned dict always carries the citations/evidence and latency breakdown.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from retriever import build_retriever, DEFAULT_TOP_K, Retriever
from decision import decide_action
from thresholds import ABSTAIN_MESSAGE
from prompt import build_messages, parse_and_validate, OutputValidationError
from model_client import ModelClient


class RagAnswerPipeline:
    """End-to-end RAG: retrieval + deterministic decision + (optional) model."""

    def __init__(self, top_k: int = DEFAULT_TOP_K,
                 retriever: Optional[Retriever] = None,
                 model_client: Optional[ModelClient] = None):
        self.top_k = top_k
        self.retriever = retriever if retriever is not None else build_retriever()
        self.model_client = model_client if model_client is not None else ModelClient()

    def answer(self, question: str, top_k: int = None) -> Dict:
        k = top_k if top_k is not None else self.top_k
        retrieval = self.retriever.retrieve(question, top_k=k)
        passages = retrieval["retrieved_passages"]
        decision = decide_action(question, passages)
        action = decision["action"]

        base = {
            "question": question,
            "retrieval_method": retrieval["retrieval_method"],
            "retrieved_passages": passages,
            "top_source": passages[0]["source"] if passages else None,
            "signals": decision["signals"],
            "thresholds": decision["thresholds"],
            "retrieval_latency_ms": retrieval["latency_ms"],
            "decision_reason": decision["reason"],
        }

        # --- deterministic terminal actions (no model call) ---------------
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

        if action == "CLARIFICATION_REQUIRED":
            clarifying = (
                "This question does not specify whether the purchase is for "
                "GOODS or SERVICES, and the applicable rule differs between the "
                "two. Could you confirm which type of purchase this is?"
            )
            return {
                **base,
                "action": "CLARIFICATION_REQUIRED",
                "answer": clarifying,
                "evidence": [{"source": p["source"], "text": p["text"]}
                             for p in passages],
                "citations": sorted({p["source"] for p in passages}),
                "confidence": "n/a",
                "model_status": "NOT_CALLED",
                "model_latency_ms": 0.0,
                "model_usage": {},
            }

        # --- ANSWERED_ELIGIBLE -> call the Foundation Model ----------------
        evidence_for_model = [{"source": p["source"], "text": p["text"]}
                              for p in passages]
        messages = build_messages(question, evidence_for_model)
        model_res = self.model_client.complete(messages)

        if model_res.status == "PENDING_EXECUTION":
            # No API key -> do NOT fabricate an answer.
            return {
                **base,
                "action": "PENDING_EXECUTION",
                "answer": None,
                "evidence": evidence_for_model,
                "citations": sorted({p["source"] for p in evidence_for_model}),
                "confidence": "n/a",
                "model_status": "PENDING_EXECUTION",
                "model_note": model_res.error,
                "model_config": model_res.config,
                "model_latency_ms": 0.0,
                "model_usage": {},
            }

        if model_res.status == "ERROR":
            return {
                **base,
                "action": "MODEL_ERROR",
                "answer": None,
                "evidence": evidence_for_model,
                "citations": sorted({p["source"] for p in evidence_for_model}),
                "confidence": "n/a",
                "model_status": "ERROR",
                "model_note": model_res.error,
                "model_latency_ms": model_res.latency_ms,
                "model_usage": {},
            }

        # status == OK: validate the structured reply.
        try:
            parsed = parse_and_validate(model_res.raw_text)
        except OutputValidationError as e:
            return {
                **base,
                "action": "MODEL_OUTPUT_INVALID",
                "answer": None,
                "raw_model_text": model_res.raw_text,
                "evidence": evidence_for_model,
                "citations": sorted({p["source"] for p in evidence_for_model}),
                "confidence": "n/a",
                "model_status": "OK_BUT_INVALID",
                "model_note": str(e),
                "model_latency_ms": model_res.latency_ms,
                "model_usage": model_res.usage,
            }

        return {
            **base,
            "action": parsed["action"],           # model may confirm ANSWERED or be more cautious
            "answer": parsed["answer"],
            "evidence": parsed["evidence"],
            "citations": parsed["citations"],
            "confidence": parsed["confidence"],
            "model_status": "OK",
            "model_latency_ms": model_res.latency_ms,
            "model_usage": model_res.usage,
        }


if __name__ == "__main__":
    pipe = RagAnswerPipeline()
    for q in [
        "What is the procurement card per-transaction limit?",   # answer-eligible
        "Who signs off on a $50,000 purchase?",                  # clarification
        "What is the policy on employee travel reimbursement?",  # abstain
    ]:
        out = pipe.answer(q)
        print("=" * 80)
        print("Q:", q)
        print("action        :", out["action"])
        print("model_status  :", out["model_status"])
        print("answer        :", out["answer"])
        print("citations     :", out["citations"])
