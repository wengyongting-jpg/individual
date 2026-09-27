"""
rag/retriever.py
================

STAGE 2 — Vector retrieval layer for the RAG pipeline (RETRIEVAL ONLY).

Primary retrieval uses TF-IDF vectors + cosine similarity.

For procurement questions containing explicit monetary amounts, the retriever
also uses deterministic numeric-range and goods/services matching to improve
ranking of the most relevant policy passage.

The retrieval score exposed to downstream decision-making is the final
ranking score:

    ranking_score = cosine_score
                    + numeric_match_bonus
                    + domain_match_bonus

The original TF-IDF cosine score is preserved separately as
"cosine_score".
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from chunker import Chunk, load_chunks, POLICY_DIR


DEFAULT_TOP_K = 3

# Ranking bonuses.
# These affect retrieval ranking and downstream decision signals.
NUMERIC_MATCH_BONUS = 0.20
DOMAIN_MATCH_BONUS = 0.15


class Retriever(ABC):
    """Abstract retrieval interface."""

    retrieval_method: str = "abstract"

    @abstractmethod
    def retrieve(self, question: str, top_k: int = DEFAULT_TOP_K) -> Dict:
        raise NotImplementedError


class TfidfRetriever(Retriever):
    """
    TF-IDF + cosine-similarity retriever with numeric-aware
    and domain-aware ranking.
    """

    retrieval_method = "tfidf_cosine"

    def __init__(
        self,
        policy_dir: str = POLICY_DIR,
        chunks: Optional[List[Chunk]] = None,
    ):
        self.policy_dir = policy_dir

        self.chunks: List[Chunk] = (
            chunks if chunks is not None else load_chunks(policy_dir)
        )

        if not self.chunks:
            raise ValueError("No chunks were loaded; cannot build a retriever.")

        self._texts = [c.chunk_text for c in self.chunks]

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            token_pattern=r"(?u)\$?\b\w[\w,\.]*\b",
        )

        self.doc_matrix = self.vectorizer.fit_transform(self._texts)

    @property
    def num_chunks(self) -> int:
        return len(self.chunks)

    @property
    def num_documents(self) -> int:
        return len({c.source_document for c in self.chunks})

    # ------------------------------------------------------------------
    # Numeric / monetary matching
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_amounts(text: str) -> List[float]:
        """Extract numeric amounts from a question."""

        matches = re.findall(
            r"\d[\d,]*(?:\.\d+)?",
            text,
        )

        amounts: List[float] = []

        for value in matches:
            try:
                amounts.append(
                    float(value.replace(",", ""))
                )
            except ValueError:
                continue

        return amounts

    @staticmethod
    def _extract_money_ranges(
        text: str,
    ) -> List[Tuple[Optional[float], Optional[float]]]:
        """
        Extract monetary ranges from policy text.

        Examples:
            "$25,000 to $74,999.99" -> (25000, 74999.99)
            "$121,200 or more"      -> (121200, None)
            "below $25,000"         -> (None, 25000)
        """

        text_lower = text.lower()

        ranges: List[
            Tuple[Optional[float], Optional[float]]
        ] = []

        # Explicit ranges:
        # "$25,000 to $74,999.99"
        # "$25,000 - $74,999.99"
        range_pattern = re.compile(
            r"\$?\s*(\d[\d,]*(?:\.\d+)?)"
            r"\s*(?:to|-)\s*"
            r"\$?\s*(\d[\d,]*(?:\.\d+)?)"
        )

        for match in range_pattern.finditer(text_lower):
            try:
                lower = float(
                    match.group(1).replace(",", "")
                )

                upper = float(
                    match.group(2).replace(",", "")
                )

                ranges.append((lower, upper))

            except ValueError:
                continue

        # "$121,200 or more"
        # "$121,200 or above"
        # "$121,200+"
        open_lower_pattern = re.compile(
            r"\$?\s*(\d[\d,]*(?:\.\d+)?)"
            r"\s*(?:or\s+more|or\s+above|\+)"
        )

        for match in open_lower_pattern.finditer(text_lower):
            try:
                lower = float(
                    match.group(1).replace(",", "")
                )

                ranges.append((lower, None))

            except ValueError:
                continue

        # "below $25,000"
        # "under $25,000"
        # "less than $25,000"
        open_upper_pattern = re.compile(
            r"(?:below|under|less\s+than)\s+"
            r"\$?\s*(\d[\d,]*(?:\.\d+)?)"
        )

        for match in open_upper_pattern.finditer(text_lower):
            try:
                upper = float(
                    match.group(1).replace(",", "")
                )

                ranges.append((None, upper))

            except ValueError:
                continue

        # "above $75,000"
        # "over $75,000"
        # "exceeds $75,000"
        open_lower_pattern_2 = re.compile(
            r"(?:above|over|exceeds)\s+"
            r"\$?\s*(\d[\d,]*(?:\.\d+)?)"
        )

        for match in open_lower_pattern_2.finditer(text_lower):
            try:
                lower = float(
                    match.group(1).replace(",", "")
                )

                ranges.append((lower, None))

            except ValueError:
                continue

        return ranges

    @classmethod
    def _numeric_match(
        cls,
        question: str,
        chunk_text: str,
    ) -> bool:
        """Return True if a question amount falls within a chunk range."""

        question_amounts = cls._extract_amounts(question)

        if not question_amounts:
            return False

        ranges = cls._extract_money_ranges(chunk_text)

        if not ranges:
            return False

        for amount in question_amounts:

            for lower, upper in ranges:

                lower_ok = (
                    lower is None
                    or amount >= lower
                )

                upper_ok = (
                    upper is None
                    or amount <= upper
                )

                if lower_ok and upper_ok:
                    return True

        return False

    # ------------------------------------------------------------------
    # Goods / services domain matching
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_domain(text: str) -> Optional[str]:
        """
        Detect procurement domain from question text.

        For policy chunks, source-document metadata is preferred because
        phrases such as "Central Procurement Services" can appear inside
        a goods policy document.
        """

        text_lower = text.lower()

        has_goods = bool(
            re.search(
                r"\bgoods?\b",
                text_lower,
            )
        )

        has_services = bool(
            re.search(
                r"\bservices?\b",
                text_lower,
            )
        )

        if has_goods and not has_services:
            return "goods"

        if has_services and not has_goods:
            return "services"

        return None

    @classmethod
    def _domain_match(
        cls,
        question: str,
        chunk: Chunk,
    ) -> bool:
        """
        Match question domain against policy chunk domain.

        Source filenames are preferred:

            *_goods_*
            *_services_*

        This avoids falsely identifying a goods policy as a services
        policy merely because it contains the phrase
        "Central Procurement Services".
        """

        question_domain = cls._detect_domain(question)

        if question_domain is None:
            return False

        source_lower = chunk.source_document.lower()

        if "_goods_" in source_lower:
            chunk_domain = "goods"

        elif "_services_" in source_lower:
            chunk_domain = "services"

        else:
            chunk_domain = cls._detect_domain(
                chunk.chunk_text
            )

        if chunk_domain is None:
            return False

        return question_domain == chunk_domain

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> Dict:

        start = time.perf_counter()

        # --------------------------------------------------------------
        # Original TF-IDF retrieval
        # --------------------------------------------------------------

        q_vec = self.vectorizer.transform(
            [question]
        )

        sims = cosine_similarity(
            q_vec,
            self.doc_matrix,
        )[0]

        # --------------------------------------------------------------
        # Add deterministic ranking signals
        # --------------------------------------------------------------

        indexed = []

        for idx, cosine_score in enumerate(sims):

            cosine_score = float(cosine_score)

            chunk = self.chunks[idx]

            numeric_match = self._numeric_match(
                question,
                chunk.chunk_text,
            )

            domain_match = self._domain_match(
                question,
                chunk,
            )

            numeric_bonus = (
                NUMERIC_MATCH_BONUS
                if numeric_match
                else 0.0
            )

            domain_bonus = (
                DOMAIN_MATCH_BONUS
                if domain_match
                else 0.0
            )

            ranking_score = (
                cosine_score
                + numeric_bonus
                + domain_bonus
            )

            indexed.append(
                (
                    idx,
                    cosine_score,
                    numeric_match,
                    domain_match,
                    ranking_score,
                )
            )

        # --------------------------------------------------------------
        # Deterministic sorting
        # --------------------------------------------------------------

        indexed.sort(
            key=lambda item: (
                -round(item[4], 6),
                -round(item[1], 6),
                self.chunks[item[0]].source_document,
                self.chunks[item[0]].chunk_id,
            )
        )

        # --------------------------------------------------------------
        # Build output
        # --------------------------------------------------------------

        retrieved_passages: List[Dict] = []

        for rank, (
            idx,
            cosine_score,
            numeric_match,
            domain_match,
            ranking_score,
        ) in enumerate(
            indexed[:top_k],
            start=1,
        ):

            chunk = self.chunks[idx]

            retrieved_passages.append(
                {
                    "rank": rank,
                    "source": chunk.source_document,
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.chunk_text,

                    # Final score consumed by Stage 3.
                    "score": round(
                        cosine_score,
                        6,
                    ),
                    "ranking_score": round(
                        ranking_score,
                        6,
                        ),
                        "numeric_match": numeric_match,
                        "domain_match": domain_match,

                    # Original lexical similarity for
                    # explicitly for diagnostics/reporting.
                    "cosine_score": round(
                        cosine_score,
                        6,
                    ),
                }
            )

        latency_ms = (
            time.perf_counter() - start
        ) * 1000.0

        return {
            "question": question,
            "retrieved_passages": retrieved_passages,
            "latency_ms": round(
                latency_ms,
                3,
            ),
            "top_k": top_k,
            "retrieval_method": self.retrieval_method,
        }


def build_retriever(
    policy_dir: str = POLICY_DIR,
) -> Retriever:

    return TfidfRetriever(
        policy_dir=policy_dir
    )


if __name__ == "__main__":

    r = build_retriever()

    print(
        f"Built {r.retrieval_method} retriever: "
        f"{r.num_documents} documents, "
        f"{r.num_chunks} chunks.\n"
    )

    demo = (
        "How many supplier quotations are required "
        "for a $100,000 goods purchase?"
    )

    out = r.retrieve(demo)

    print(
        f"Q: {out['question']}"
    )

    print(
        f"latency: {out['latency_ms']} ms "
        f"| method: {out['retrieval_method']}\n"
    )

    for p in out["retrieved_passages"]:

        print(
            f"[{p['rank']}] "
            f"score={p['score']} "
            f"cosine={p['cosine_score']}  "
            f"{p['source']}  "
            f"({p['chunk_id']})"
        )

        print(
            f"     {p['text'][:140]}..."
        )