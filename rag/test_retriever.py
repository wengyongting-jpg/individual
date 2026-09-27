"""
rag/test_retriever.py
=====================

STAGE 2 — Manual inspection of retrieval behaviour (NOT a scored evaluation).

This script runs a few representative questions through the retriever so we can
eyeball WHAT gets retrieved for each of the four question categories used in the
project:

    1. normal                -> expect a clearly relevant passage on top
    2. boundary              -> exact-dollar tier question
    3. ambiguous             -> no goods/services stated; retrieval alone
                                cannot disambiguate (important for later stages)
    4. insufficient_evidence -> topic absent from the corpus; we want to SEE
                                whether retrieval still surfaces near-miss
                                passages (it usually does — that motivates the
                                later abstention threshold)

These questions are hand-written for inspection only. Nothing here reads or
modifies ground_truth.json, and retrieval never sees any expected answer.

Run with:
    python rag/test_retriever.py
"""

from __future__ import annotations

from retriever import build_retriever


SAMPLE_QUESTIONS = [
    ("normal",
     "How many quotations are needed for a large goods purchase over $75,000?"),
    ("boundary",
     "What are the rules for a goods purchase of exactly $121,200?"),
    ("ambiguous",
     "Who signs off on a $50,000 purchase?"),
    ("insufficient_evidence",
     "How many years must procurement records be kept before they are destroyed?"),
]


def main() -> None:
    retriever = build_retriever()
    print(f"Retriever: {retriever.retrieval_method} | "
          f"{retriever.num_documents} docs | {retriever.num_chunks} chunks\n")

    for category, question in SAMPLE_QUESTIONS:
        out = retriever.retrieve(question, top_k=3)
        print("=" * 78)
        print(f"CATEGORY : {category}")
        print(f"QUESTION : {question}")
        print(f"LATENCY  : {out['latency_ms']} ms")
        print("-" * 78)
        for p in out["retrieved_passages"]:
            text = p["text"]
            snippet = text[:200] + (" ..." if len(text) > 200 else "")
            print(f"[Rank {p['rank']}] cosine={p['score']}")
            print(f"  source : {p['source']}  ({p['chunk_id']})")
            print(f"  text   : {snippet}")
        print()


if __name__ == "__main__":
    main()
