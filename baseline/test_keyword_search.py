"""
baseline/test_keyword_search.py
===============================

A small, beginner-friendly test script for the non-AI keyword baseline.

It is NOT a formal evaluation against ground_truth.json (that comes later,
once RAG exists, so both systems are scored the same way). This script just
lets you eyeball how the keyword baseline behaves on a handful of questions,
including the three kinds of cases in the project:

  - normal / boundary  -> we expect a relevant passage on top
  - ambiguous          -> keyword search cannot tell goods vs services apart
  - insufficient        -> the topic is absent, so matches should be weak/none

Run it with:

    python baseline/test_keyword_search.py
"""

from keyword_search import KeywordSearch, print_result


# A few sample questions grouped by the kind of case they represent.
SAMPLE_QUESTIONS = [
    # --- normal look-ups (a single document should clearly win) ---
    ("normal",        "How many supplier quotations are required for a $100,000 goods purchase?"),
    ("normal",        "What is the SynthCorp Procurement Card per-transaction limit?"),
    ("normal",        "How does a supplier become an Approved Supplier?"),

    # --- boundary cases (exact dollar amounts on a tier edge) ---
    ("boundary",      "What procurement process applies to a goods purchase of exactly $75,000?"),
    ("boundary",      "Is a PPEJ required for a non-competitive purchase of exactly $25,000?"),

    # --- ambiguous (no goods/services stated: baseline can't disambiguate) ---
    ("ambiguous",     "What procurement method applies to a purchase of $75,000?"),
    ("ambiguous",     "Who approves a $50,000 purchase?"),

    # --- insufficient evidence (topic not in the corpus) ---
    ("insufficient",  "How long must procurement records be retained before destruction?"),
    ("insufficient",  "Can an unsuccessful supplier appeal a procurement decision?"),
]


def main() -> None:
    engine = KeywordSearch()
    print(
        f"Indexed {engine.num_documents} policy documents "
        f"into {len(engine.passages)} passages.\n"
    )

    for category, question in SAMPLE_QUESTIONS:
        print(f"### CATEGORY: {category}")
        result = engine.search(question, top_k=3)
        print_result(result)


if __name__ == "__main__":
    main()
