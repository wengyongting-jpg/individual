"""
rag/rag_pipeline.py
===================

RAG pipeline wrapper.

STAGE 2 established: User Question -> chunking -> vector retrieval -> Top-K.
STAGE 3 adds the deterministic DECISION LAYER on top of retrieval:

    User Question
          |
      vector retrieval (Top-K)                 [rag/retriever.py]
          |
      compute signals (top_score, margin)      [rag/signals.py]
          |
      decide_action() -- clarification first,  [rag/decision.py]
                         then frozen-threshold  [rag/thresholds.py]
                         abstention
          |
      { action, evidence, signals }

There is still NO Foundation Model call and NO answer generation here. When the
action is ANSWERED_ELIGIBLE it means a LATER stage may ask a model to answer
using the retrieved evidence; the pipeline itself does not answer.
"""

from __future__ import annotations

from typing import Dict

from retriever import build_retriever, DEFAULT_TOP_K, Retriever
from decision import decide_action


class RagPipeline:
    """Retrieval + deterministic decision layer. No LLM, no API."""

    def __init__(self, top_k: int = DEFAULT_TOP_K, retriever: Retriever = None):
        self.top_k = top_k
        self.retriever = retriever if retriever is not None else build_retriever()

    def run(self, question: str, top_k: int = None) -> Dict:
        k = top_k if top_k is not None else self.top_k
        retrieval = self.retriever.retrieve(question, top_k=k)
        passages = retrieval["retrieved_passages"]

        decision = decide_action(question, passages)

        return {
            "question": question,
            "stage": "retrieval_plus_decision",
            "foundation_model_called": False,
            "retrieval_method": retrieval["retrieval_method"],
            "retrieved_passages": passages,
            "top_source": passages[0]["source"] if passages else None,
            "action": decision["action"],
            "reason": decision["reason"],
            "signals": decision["signals"],
            "thresholds": decision["thresholds"],
            "abstain_message": decision["message"],
            "latency_ms": retrieval["latency_ms"],
        }


if __name__ == "__main__":
    pipe = RagPipeline()
    for q in [
        "What is the SynthCorp Procurement Card per-transaction limit?",
        "Who signs off on a $50,000 purchase?",
        "What is the policy on employee travel reimbursement rates?",
    ]:
        out = pipe.run(q)
        print(f"Q: {q}")
        print(f"   action={out['action']}  signals={out['signals']}")
        print(f"   reason={out['reason']}")
        print()
