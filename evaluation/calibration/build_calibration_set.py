"""
evaluation/calibration/build_calibration_set.py
================================================

STAGE 3 — Build a SEPARATE synthetic calibration set used ONLY to calibrate the
abstention thresholds. This set is deliberately DISJOINT from the 22 locked
ground-truth cases: the ground-truth questions are never read or reused here.

Two classes of calibration question are produced:

  * ``in_corpus``      : questions that SHOULD be answerable, generated
                         mechanically from the policy paragraphs themselves.
                         Because they are derived from real chunks, strong
                         retrieval is expected. These define the "genuine hit"
                         score distribution.

  * ``out_of_corpus``  : questions on procurement-adjacent topics KNOWN to be
                         absent from this corpus, taken from a fixed,
                         hand-authored list of GENERAL off-corpus themes. These
                         define the "no real evidence" score distribution.

Determinism: the generator uses fixed templates and a fixed topic list, iterated
in sorted order. Running it twice produces byte-identical output.

IMPORTANT GUARDRAILS
  * Does NOT read ground_truth.json.
  * Does NOT modify the 15 policy documents (read-only).
  * The out_of_corpus themes are written to be plausible-but-absent and are NOT
    copies of the 5 ground-truth ABSTAIN questions.

Run:
    python evaluation/calibration/build_calibration_set.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "rag"))

from chunker import load_chunks  # noqa: E402

OUTPUT_PATH = os.path.join(HERE, "calibration_questions.json")

# A short, general list of procurement-adjacent topics that are NOT covered by
# the 15-document corpus. These are hand-authored generic themes (not copies of
# any ground-truth question) used to observe how the retriever scores questions
# with no genuine supporting evidence. Kept fixed for reproducibility.
OUT_OF_CORPUS_THEMES = [
    "warranty claims and product return procedures for delivered goods",
    "standard payment terms and invoice due dates for suppliers",
    "guaranteed delivery timelines and late-delivery penalties",
    "sales tax and HST coding on procurement invoices",
    "environmental sustainability scoring of bids",
    "cybersecurity certification required from software vendors",
    "travel and expense reimbursement rates for staff",
    "employee corporate credit card rewards and points policy",
    "supplier diversity quota targets and reporting",
    "data privacy breach notification timelines for vendors",
    "physical office access badges for on-site contractors",
    "translation of contracts into languages other than English",
]


def _first_sentence(text: str) -> str:
    """Return the first sentence-ish fragment of a paragraph."""
    # Split on a period followed by a space + capital, else take whole text.
    parts = re.split(r"(?<=[.:])\s+", text.strip())
    return parts[0].strip() if parts else text.strip()


def _looks_like_title(text: str) -> bool:
    return text.strip().upper().startswith("SYNTHCORP PROCUREMENT POLICY")


def _topic_from_chunk(text: str) -> str:
    """
    Derive a short topic phrase from a chunk to seed an in-corpus question.

    Prefer an ALL-CAPS section heading if the chunk starts with one (e.g.
    'TRANSACTION LIMIT ...'), otherwise fall back to the first sentence.
    """
    stripped = text.strip()
    m = re.match(r"^([A-Z][A-Z0-9 ,\-/&]{3,})(?=\s[A-Z][a-z]|\s—|$)", stripped)
    if m:
        heading = m.group(1).strip(" -—,")
        if 3 <= len(heading) <= 60:
            return heading.lower()
    return _first_sentence(stripped)


# Fixed question templates for in-corpus questions. Deterministic.
IN_CORPUS_TEMPLATES = [
    "What does the procurement policy say about {topic}?",
    "What are the rules regarding {topic}?",
    "Explain the policy on {topic}.",
]

OUT_OF_CORPUS_TEMPLATES = [
    "What is the procurement policy on {topic}?",
    "What are the rules for {topic}?",
]


def build_calibration_set() -> Dict:
    chunks = load_chunks()  # read-only load of the policy documents

    in_corpus: List[Dict] = []
    seq = 0
    for chunk in chunks:
        text = chunk.chunk_text
        # Skip pure title chunks (too generic to form a specific question).
        if _looks_like_title(text) and len(text) < 90:
            continue
        topic = _topic_from_chunk(text)
        if not topic or len(topic) < 4:
            continue
        template = IN_CORPUS_TEMPLATES[seq % len(IN_CORPUS_TEMPLATES)]
        seq += 1
        in_corpus.append(
            {
                "calib_id": f"IN{seq:03d}",
                "klass": "in_corpus",
                "question": template.format(topic=topic),
                "derived_from_source": chunk.source_document,
                "derived_from_chunk_id": chunk.chunk_id,
            }
        )

    out_corpus: List[Dict] = []
    oc = 0
    for theme in OUT_OF_CORPUS_THEMES:
        for template in OUT_OF_CORPUS_TEMPLATES:
            oc += 1
            out_corpus.append(
                {
                    "calib_id": f"OUT{oc:03d}",
                    "klass": "out_of_corpus",
                    "question": template.format(topic=theme),
                    "theme": theme,
                }
            )

    questions = in_corpus + out_corpus

    # Content hash for provenance (so calibrated thresholds can cite exactly
    # which calibration set produced them).
    payload_for_hash = json.dumps(
        [q["question"] for q in questions], ensure_ascii=False
    ).encode("utf-8")
    content_hash = hashlib.sha256(payload_for_hash).hexdigest()

    return {
        "_meta": {
            "purpose": (
                "Separate synthetic calibration set for Stage 3 threshold "
                "calibration. DISJOINT from the 22 locked ground-truth cases; "
                "ground_truth.json is never read to build this set."
            ),
            "num_in_corpus": len(in_corpus),
            "num_out_of_corpus": len(out_corpus),
            "num_total": len(questions),
            "deterministic": True,
            "content_sha256": content_hash,
        },
        "questions": questions,
    }


def main() -> None:
    data = build_calibration_set()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    m = data["_meta"]
    print("Built calibration set:")
    print(f"  in_corpus     : {m['num_in_corpus']}")
    print(f"  out_of_corpus : {m['num_out_of_corpus']}")
    print(f"  total         : {m['num_total']}")
    print(f"  sha256        : {m['content_sha256']}")
    print(f"  saved to      : {OUTPUT_PATH}")
    print("\nSample in_corpus questions:")
    for q in data["questions"][:4]:
        print(f"  [{q['calib_id']}] {q['question']}")
    print("Sample out_of_corpus questions:")
    for q in [x for x in data["questions"] if x["klass"] == "out_of_corpus"][:3]:
        print(f"  [{q['calib_id']}] {q['question']}")


if __name__ == "__main__":
    main()
