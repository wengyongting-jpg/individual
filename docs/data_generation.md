# Synthetic Data Generation Methodology

The corpus and ground truth are synthetic by design: a real enterprise could
not provide internal procurement policies for an academic project, so a
controlled corpus was authored. This document records exactly how, so the
evaluation's credibility — and its ceiling effects — can be judged.

## 1. Who and how

All 16 documents were **authored manually by the project author** for PE6201.
There is no generator script and no model was used to produce the policy
text: the rules, thresholds, and deliberate defects were designed
deliberately rather than sampled. Every file begins with a fixed header:

```text
SYNTHCORP PROCUREMENT POLICY — <TITLE>
STATUS: SYNTHETIC DOCUMENT FOR ACADEMIC PROTOTYPE ONLY.
```

The `STATUS` paragraph is boilerplate (stripped at chunk time by
`rag/chunker.py`); the remainder is policy content.

## 2. Corpus shape (verifiable from the files)

- **16 policy documents — 15 current policy documents + 1 superseded policy
  edition** — in `15 policy files/`, ~24,500 characters total.
- Lengths are deliberately comparable: each document is 1.2–2.0K characters
  (18–26 content paragraphs), written as short, topically focused paragraphs
  (one tier, one rule per paragraph) so paragraph-level chunking keeps each
  rule intact.
- The corpus covers: a **goods track** (files 01–04: thresholds/approval,
  quotes/ITQ, PO documentation, non-competitive/PPEJ), a **services track**
  (05–07: thresholds/approval, non-competitive/PPEJ, templates/contracts),
  and **cross-cutting policies** (08 value calculation, 09 procurement
  cards, 10 supplier fairness, 11 approved suppliers, 12 provincial trade,
  13 conflict of interest, 14 governance roles, 15 research-grant
  purchases). File 16 is a **2019, explicitly SUPERSEDED edition** of
  file 12 stating a different rule.

## 3. How edge cases were planted

The corpus was designed *before* the system, with the required failure modes
built into the documents rather than faked in questions:

| Phenomenon | How it exists in the corpus | Tested by |
|---|---|---|
| Goods vs services divergence | Same dollar amounts map to different methods, quote counts, and approvers across the two tracks | TC11–TC15 (clarification) |
| Numeric boundary sensitivity | Explicit tiers with exact edges ($25,000; $100,000; $121,200) | TC01–TC05 (on/around boundaries) |
| Vocabulary mismatch / distractors | Related documents reuse the same vocabulary ("procurement value", "goods purchase", "$121,200") while only one contains the rule | TC06–TC08; see `docs/retrieval_edge_cases.md` |
| Absent but plausible | Five plausible procurement topics are simply **not covered** anywhere (disciplinary action, supplier appeals, supplier insurance, record retention, FX rules) | TC16–TC20 (abstention) |
| Superseded policy | File 16 is a realistic old edition, labelled SUPERSEDED, with a different preference rule; file 12 cross-references it | TC21 |
| Genuine cross-document conflict | File 14's gift guidance directly contradicts file 13's absolute gift ban **and says in its own text that it is unreconciled** | TC22 |

The last two were added in the one disclosed, dated amendment
(2026-09-19) recorded in `ground_truth.json`'s `_meta.amendment`; earlier
drafts only simulated these defects inside questions, which would have
meant testing against documents that did not actually contain them.

## 4. Ground truth construction

`ground_truth.json` holds 22 cases in five balanced categories
(5 normal, 5 boundary, 5 ambiguous, 5 insufficient-evidence,
2 conflicting/outdated), each specifying:

- `question`;
- `expected_action` — one of `ANSWERED`, `CLARIFICATION_REQUIRED`,
  `ABSTAIN`;
- `expected_source` — the document(s) a grounded answer must cite (empty by
  design for the five insufficient-evidence cases, since the answer is
  absent from the corpus);
- `expected_answer` — the rule a correct answer must contain (empty by
  design for the ten non-answerable cases).

The set was **locked before the RAG system was implemented or evaluated**
(`"locked": true` in `_meta`) so cases could not be adjusted to fit system
output. Thresholds were selected only on a disjoint 90-question calibration
set; the 22 GT cases were used once, for measurement. Answer texts were
human-graded against `expected_answer`
(`evaluation/results/rule_accuracy_manual.json`).

## 5. Known ceiling effects (why results must not be generalised)

A designed corpus makes some real-world problems easier:

1. **Single authorial voice and consistent terminology** — real policy
   libraries mix authors, house styles, and synonyms over years; the saved
   Stage 2 diagnostic shows vocabulary mismatch still occurs (TC06–TC08),
   but a real corpus would exhibit far more.
2. **Small, clean, on-topic collection** — every file is a genuine
   procurement policy; real corpora include drafts, templates, newsletters,
   and near-duplicate files that act as distractors.
3. **Explicit round thresholds and self-describing conflicts** — real rules
   are often implicit, cross-referenced, or silently contradictory (file 14
   deliberately announces its own unreconciled status).
4. **No scale** — 16 short documents vs hundreds or thousands of long ones,
   where ranking and chunk-boundary problems dominate.

These are acknowledged in the report's Limitations rather than hidden:
100% routing/grounding on this corpus supports the architecture, not
deployment readiness.
