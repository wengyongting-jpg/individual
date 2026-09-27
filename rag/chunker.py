"""
rag/chunker.py
==============

STAGE 2 — Deterministic document chunking for the RAG retrieval layer.

This module loads the SAME 15 SynthCorp policy documents used by the keyword
baseline and cuts each one into small, retrievable chunks. It does NOT modify
the policy files in any way — it only reads them.

Design choices (kept deliberately simple and reproducible):

* We chunk on natural PARAGRAPH boundaries (blank lines), because the policy
  files are already written as short, topically-focused paragraphs (e.g. one
  paragraph per tier, one per rule). Paragraph chunking therefore keeps each
  rule intact instead of splitting a rule across chunks.
* We skip the fixed "STATUS: SYNTHETIC DOCUMENT ..." disclaimer paragraph that
  is identical in every file, so it does not add noise to retrieval. This is
  the SAME boilerplate the baseline skips, keeping the two systems comparable
  on the same effective corpus.
* Chunking is fully deterministic: same files in -> same chunks out, in the
  same order, every run.

Each chunk carries metadata:
    source_document : the .txt filename
    chunk_id        : stable id, "<filename>::<index>" (index is per-document)
    chunk_text      : the paragraph text (whitespace normalised to single lines)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from typing import Dict, List


# The 15 policy files live at <repo>/15 policy files/. This module is in
# <repo>/rag/, so go up one level then into the policy folder. This is the
# SAME corpus path the baseline uses.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
POLICY_DIR = os.path.join(REPO_ROOT, "15 policy files")


@dataclass
class Chunk:
    """One retrievable chunk of a policy document."""
    source_document: str
    chunk_id: str
    chunk_text: str

    def to_dict(self) -> Dict:
        return asdict(self)


def _normalise_whitespace(text: str) -> str:
    """Collapse internal newlines/multiple spaces into single spaces."""
    return " ".join(text.split())


# Lines that are pure boilerplate and carry no policy meaning. In every file
# the title line, a STATUS line, and a 3-line "This document is fictional ..."
# disclaimer are packed into the FIRST block with no blank line between them,
# so a block-level skip is not enough — we must strip these at the LINE level.
# The human-readable title line (e.g. "SYNTHCORP PROCUREMENT POLICY — GOODS:
# ...") is genuine, useful content and is KEPT.
_BOILERPLATE_LINE_PREFIXES = (
    "STATUS: SYNTHETIC DOCUMENT",
    "This document is fictional",
    "the real policy of any real institution",
    "coincidental and for demonstration purposes",
)


def _strip_boilerplate_lines(block: str) -> str:
    """Remove the synthetic-document disclaimer lines from a block, keeping the
    rest (including any real title line). Returns the cleaned block text."""
    kept_lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(pfx) for pfx in _BOILERPLATE_LINE_PREFIXES):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def _split_into_paragraphs(content: str) -> List[str]:
    """
    Split a document on blank lines into paragraph blocks, then strip the fixed
    synthetic-document disclaimer lines so they do not pollute retrieval.

    A block that is nothing but boilerplate becomes empty and is dropped. Blocks
    that mix a real title/content line with disclaimer lines keep the real part.
    """
    raw_blocks = re.split(r"\n\s*\n", content)
    paragraphs: List[str] = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        cleaned = _strip_boilerplate_lines(block)
        if not cleaned:
            continue
        paragraphs.append(_normalise_whitespace(cleaned))
    return paragraphs


def load_chunks(policy_dir: str = POLICY_DIR) -> List[Chunk]:
    """
    Load all 15 policy documents and return a deterministic list of Chunks.

    Files are processed in sorted filename order; chunks within a file are
    numbered in document order. This guarantees a stable, reproducible index.
    """
    if not os.path.isdir(policy_dir):
        raise FileNotFoundError(
            f"Policy folder not found: {policy_dir}\n"
            f"Expected the 15 policy .txt files there."
        )

    filenames = sorted(
        f for f in os.listdir(policy_dir) if f.lower().endswith(".txt")
    )

    chunks: List[Chunk] = []
    for filename in filenames:
        path = os.path.join(policy_dir, filename)
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        for idx, paragraph in enumerate(_split_into_paragraphs(content)):
            chunks.append(
                Chunk(
                    source_document=filename,
                    chunk_id=f"{filename}::{idx}",
                    chunk_text=paragraph,
                )
            )
    return chunks


if __name__ == "__main__":
    # Simple manual inspection: how many chunks per document?
    chunks = load_chunks()
    from collections import Counter

    per_doc = Counter(c.source_document for c in chunks)
    print(f"Loaded {len(chunks)} chunks from {len(per_doc)} documents "
          f"in:\n  {POLICY_DIR}\n")
    for doc in sorted(per_doc):
        print(f"  {per_doc[doc]:>2} chunks  {doc}")
    print("\nFirst chunk example:")
    print(f"  chunk_id: {chunks[0].chunk_id}")
    print(f"  source  : {chunks[0].source_document}")
    print(f"  text    : {chunks[0].chunk_text[:120]}...")
