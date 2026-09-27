"""
baseline/keyword_search.py
===========================

NON-AI BASELINE for the Grounded Enterprise Policy & Procedure Assistant (PE6201).

This is a deliberately SIMPLE, traditional keyword-based search over the SAME
15 SynthCorp procurement policy documents used by the RAG system.

What this file does NOT use (on purpose):
  - No LLM / GPT / chat model
  - No embeddings / vector database
  - No external AI API
  - No machine-learning library

It only uses Python's standard library. Everything is deterministic:
the same question will always produce exactly the same ranking.

--------------------------------------------------------------------------
HOW IT WORKS (in 6 small steps)
--------------------------------------------------------------------------
1. LOAD    : read all 15 .txt policy files from "15 policy files/".
2. SPLIT   : cut each document into small passages (paragraphs).
3. KEYWORDS: turn the user's question into a set of keywords
             (lowercase, remove punctuation, drop common "stop words").
4. SCORE   : for every passage, count how many query keywords appear in it
             (a simple, transparent overlap score, with a small bonus for
             rare words so distinctive terms matter more).
5. RANK    : sort passages by score, highest first (deterministic tie-break).
6. RETURN  : the top passages, their source document, which keywords matched,
             and how long the search took (latency in milliseconds).

Run it directly to try the built-in demo questions:

    python baseline/keyword_search.py

Or ask your own question:

    python baseline/keyword_search.py "How many quotes for a $100,000 goods purchase?"
"""

from __future__ import annotations

import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List


# --------------------------------------------------------------------------
# 0. Where the policy documents live
# --------------------------------------------------------------------------
# The 15 policy files sit in a folder next to the project root:
#   <repo>/15 policy files/*.txt
# This file lives in <repo>/baseline/, so we go up one level then into the
# policy folder. This keeps the baseline using the EXACT same corpus.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
POLICY_DIR = os.path.join(REPO_ROOT, "15 policy files")


# --------------------------------------------------------------------------
# 1. A tiny list of common English "stop words"
# --------------------------------------------------------------------------
# These words appear in almost every sentence, so they are useless for
# matching. We remove them from both the question and the documents when
# building keywords. (Kept short and readable on purpose.)
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "of", "to", "in",
    "on", "for", "with", "at", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those", "it", "its",
    "as", "how", "what", "who", "when", "where", "which", "why", "does",
    "do", "did", "can", "could", "should", "would", "must", "may", "will",
    "shall", "i", "you", "he", "she", "we", "they", "my", "your", "his",
    "her", "our", "their", "me", "us", "them", "about", "into", "than",
    "so", "such", "any", "each", "per",
}


# --------------------------------------------------------------------------
# 2. Data structures for the results (simple containers)
# --------------------------------------------------------------------------
@dataclass
class PassageResult:
    """One matching passage returned by the search."""
    rank: int
    score: float
    source_document: str          # e.g. "01_goods_thresholds_and_approval.txt"
    matched_keywords: List[str]   # which query keywords appeared here
    passage: str                  # the actual text of the passage


@dataclass
class SearchResult:
    """The full result of one search."""
    question: str
    query_keywords: List[str]
    results: List[PassageResult]
    latency_ms: float
    num_documents: int
    num_passages: int = 0
    corpus_dir: str = ""


# --------------------------------------------------------------------------
# 3. Text helpers
# --------------------------------------------------------------------------
_WORD_RE = re.compile(r"[a-z0-9$,\.]+")


def tokenize(text: str) -> List[str]:
    """
    Turn a piece of text into a list of lowercase word "tokens".

    We keep letters, digits, '$', ',' and '.' so that dollar amounts like
    "$75,000" or "$121,199.99" survive as single tokens. We then also add a
    "digits only" version (e.g. "75000") so a question that types "75000"
    still matches a document that wrote "$75,000".
    """
    text = text.lower()
    raw_tokens = _WORD_RE.findall(text)

    tokens: List[str] = []
    for tok in raw_tokens:
        tok = tok.strip(".,")          # drop trailing sentence punctuation
        if not tok:
            continue
        tokens.append(tok)

        # If this token contains a number, also add a pure-digit form.
        # "$75,000" -> "75000" ; "121,199.99" -> "12119999"
        digits = re.sub(r"[^0-9]", "", tok)
        if digits and digits != tok:
            tokens.append(digits)
    return tokens


def extract_keywords(question: str) -> List[str]:
    """
    Step 3 of the pipeline: build the search keywords from the question.

    - lowercase + tokenize
    - drop stop words
    - drop very short leftover tokens
    - keep order but remove duplicates
    """
    keywords: List[str] = []
    seen = set()
    for tok in tokenize(question):
        if tok in STOP_WORDS:
            continue
        if len(tok) < 2:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        keywords.append(tok)
    return keywords


# --------------------------------------------------------------------------
# 4. The search engine itself
# --------------------------------------------------------------------------
class KeywordSearch:
    """
    A very small keyword search engine.

    On creation it loads and indexes the 15 policy documents once. After that,
    calling .search("some question") is fast and fully deterministic.
    """

    def __init__(self, policy_dir: str = POLICY_DIR):
        self.policy_dir = policy_dir
        # Each entry: {"source": filename, "text": passage text,
        #              "tokens": set_of_tokens}
        self.passages: List[Dict] = []
        # document frequency: how many passages contain a given token.
        # Used to give rare words a small bonus (a light IDF-style weight).
        self.doc_freq: Dict[str, int] = {}
        self.num_documents = 0

        self._load_and_index()

    # ---- loading & indexing -------------------------------------------
    def _load_and_index(self) -> None:
        if not os.path.isdir(self.policy_dir):
            raise FileNotFoundError(
                f"Policy folder not found: {self.policy_dir}\n"
                f"Expected the 15 policy .txt files there."
            )

        filenames = sorted(
            f for f in os.listdir(self.policy_dir) if f.lower().endswith(".txt")
        )
        self.num_documents = len(filenames)

        for filename in filenames:
            path = os.path.join(self.policy_dir, filename)
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()

            for passage_text in self._split_into_passages(content):
                tokens = set(tokenize(passage_text))
                self.passages.append(
                    {"source": filename, "text": passage_text, "tokens": tokens}
                )
                # update document frequency (count each token once per passage)
                for tok in tokens:
                    self.doc_freq[tok] = self.doc_freq.get(tok, 0) + 1

    @staticmethod
    def _split_into_passages(content: str) -> List[str]:
        """
        Cut a document into passages on blank lines (paragraph breaks).

        We skip the fixed 'SYNTHETIC DOCUMENT' disclaimer paragraph because it
        is identical in every file and would only add noise to the matching.
        """
        raw_blocks = re.split(r"\n\s*\n", content)
        passages: List[str] = []
        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue
            # Skip the boilerplate disclaimer that appears in every document.
            if block.upper().startswith("STATUS: SYNTHETIC DOCUMENT"):
                continue
            if block.startswith("This document is fictional"):
                continue
            passages.append(block)
        return passages

    # ---- scoring & ranking --------------------------------------------
    def _idf(self, token: str) -> float:
        """
        A small 'inverse document frequency' weight.

        Rare tokens (appear in few passages) get a higher weight, common
        tokens get a lower weight. This is a classic, simple, non-AI trick to
        make distinctive words (like 'ppej' or '$121,200') matter more than
        words that appear everywhere (like 'procurement').
        """
        df = self.doc_freq.get(token, 0)
        total = max(len(self.passages), 1)
        # +1 smoothing so we never divide by zero and weights stay positive.
        return math.log((total + 1) / (df + 1)) + 1.0

    def search(self, question: str, top_k: int = 3) -> SearchResult:
        """
        Search the corpus for the given question and return the top_k passages.

        Scoring (deliberately simple and explainable):
          score(passage) = sum over matched keywords of idf(keyword)
        Ranking is by score descending; ties are broken deterministically by
        (source filename, passage text) so results never change run-to-run.
        """
        start = time.perf_counter()

        keywords = extract_keywords(question)

        scored: List[PassageResult] = []
        for entry in self.passages:
            tokens = entry["tokens"]
            matched = [kw for kw in keywords if kw in tokens]
            if not matched:
                continue
            score = sum(self._idf(kw) for kw in matched)
            scored.append(
                PassageResult(
                    rank=0,  # filled in after sorting
                    score=round(score, 4),
                    source_document=entry["source"],
                    matched_keywords=matched,
                    passage=entry["text"],
                )
            )

        # Deterministic sort: higher score first; then filename; then text.
        scored.sort(
            key=lambda r: (-r.score, r.source_document, r.passage)
        )

        top = scored[:top_k]
        for i, r in enumerate(top, start=1):
            r.rank = i

        latency_ms = (time.perf_counter() - start) * 1000.0

        return SearchResult(
            question=question,
            query_keywords=keywords,
            results=top,
            latency_ms=round(latency_ms, 3),
            num_documents=self.num_documents,
            num_passages=len(self.passages),
            corpus_dir=self.policy_dir,
        )


# --------------------------------------------------------------------------
# 5. Pretty-printing a result to the terminal
# --------------------------------------------------------------------------
def print_result(result: SearchResult, max_chars: int = 400) -> None:
    line = "=" * 78
    print(line)
    print(f"QUESTION : {result.question}")
    print(f"KEYWORDS : {', '.join(result.query_keywords) or '(none)'}")
    print(
        f"CORPUS   : {result.num_documents} documents, "
        f"{result.num_passages} passages"
    )
    print(f"LATENCY  : {result.latency_ms} ms")
    print(line)

    if not result.results:
        print("No matching passages found. (A real system might ABSTAIN here.)")
        print(line)
        print()
        return

    for r in result.results:
        snippet = " ".join(r.passage.split())  # collapse whitespace for display
        if len(snippet) > max_chars:
            snippet = snippet[:max_chars].rstrip() + " ..."
        print(f"[Rank {r.rank}] score={r.score}")
        print(f"  Source          : {r.source_document}")
        print(f"  Matched keywords: {', '.join(r.matched_keywords)}")
        print(f"  Passage         : {snippet}")
        print("-" * 78)
    print()


# --------------------------------------------------------------------------
# 6. Command-line entry point + built-in demo
# --------------------------------------------------------------------------
DEMO_QUESTIONS = [
    "How many supplier quotations are required for a $100,000 goods purchase?",
    "Who approves a $50,000 consulting engagement?",
    "What is the SynthCorp Procurement Card per-transaction limit?",
    "What must be attached to a Purchase Order when it is created?",
    "How does a supplier become an Approved Supplier?",
    "What procurement process applies to a goods purchase of exactly $75,000?",
    "How long must procurement records be retained before destruction?",
]


def main(argv: List[str]) -> None:
    engine = KeywordSearch()

    if len(argv) > 1:
        # User passed their own question on the command line.
        question = " ".join(argv[1:])
        print_result(engine.search(question))
        return

    # No argument: run the demo questions so `python baseline/keyword_search.py`
    # immediately shows several examples.
    print(
        f"Loaded {engine.num_documents} policy documents "
        f"({len(engine.passages)} passages) from:\n  {engine.policy_dir}\n"
    )
    print("Running built-in demo questions. Pass your own question as an")
    print('argument to try it, e.g.:  python baseline/keyword_search.py "..."\n')
    for q in DEMO_QUESTIONS:
        print_result(engine.search(q))


if __name__ == "__main__":
    main(sys.argv)
