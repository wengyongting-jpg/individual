# Retrieval Edge Cases — Where the System Starts to Become Unreliable

PE6201 Part 2 asks not just "how accurate is retrieval?" but "where does it
break, and why?" This document examines the four required edge types on the
frozen 22-case set with measured scores.

**Reproducibility.** Every score below is recomputed, not typed in:

```bash
python evaluation/analyze_edge_cases.py        # current ranking (cosine + deterministic bonuses)
```

The pure-cosine Stage 2 diagnostic (`evaluation/results/rag_retrieval_results.json`)
is also a committed artifact. Two score fields exist by design
(`rag/retriever.py`): `score` is the raw TF-IDF cosine fed to the frozen
thresholds and signals; `ranking_score = cosine + 0.20 numeric-match bonus +
0.15 domain-match bonus` is used only for ordering. Thresholds
(`TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`) operate on raw cosine.

## Summary table

| Edge type | Case | Query (abridged) | Correct chunk | What pure lexical retrieval did | Why |
|---|---|---|---|---|---|
| Vocabulary mismatch + distractor | TC06 | "What procurement process applies to a goods purchase of exactly $75,000?" | `01_goods_thresholds_and_approval` | Top-1 `08_procurement_value_calculation` 0.2865; expected doc absent from top-3 | Terse threshold-table wording shares few exact tokens with the question; value-calculation text reuses "goods purchase" + amount language |
| Vocabulary mismatch + distractor | TC07 | same, $74,999 (just below a tier boundary) | `01_goods_thresholds_and_approval` | Top-1 `08_...` 0.2673; expected doc absent from top-3 | Same lexical gap, deliberately placed one dollar below a boundary |
| Vocabulary mismatch + wrong-track distractor | TC08 | same, exactly $121,200 (track boundary) | `01_goods_thresholds_and_approval` | Top-1 `08_...` 0.2809; services policy `05_...` also outranks the correct goods chunk | Boundary vocabulary appears in goods AND services tables; cosine cannot tell which track the numeric tier belongs to |
| Two documents needed (supersession) | TC21 | "What is the Ontario supplier preference under the provincial trade policy?" | `12_provincial_trade_policy` (current) **and** `16_..._2019_superseded` | Superseded edition ranks 1st (0.4220); current edition rank 2 (0.3991) | Both editions use near-identical vocabulary; lexical retrieval cannot know one is obsolete |
| Two documents needed (conflict) | TC22 | "Can an employee accept a gift from a supplier?" | `13_conflict_of_interest_policy` **and** `14_procurement_governance_roles` | `14_...` rank 1 (0.2731); `13_...` ranks 2–3 (0.1090, 0.1010) | Both documents genuinely address gifts with contradictory rules |
| Absent but plausible | TC18 | "What insurance or liability coverage must a supplier carry…?" | none (topic not in corpus) | Top-1 `13_conflict_of_interest_policy` only 0.1466, then contracts/supplier-program near-misses | Procurement-flavoured vocabulary ("supplier", "bid", "contracts") creates superficially plausible hits for a policy that does not exist |
| Absent but plausible | TC20 | "What currency or exchange-rate rules apply… outside Canada and the US?" | none (topic not in corpus) | Top-1 `13_...` 0.1769; trade-policy and procurement-card chunks distract | International-purchase language partially overlaps the provincial trade policy |

## 1. Vocabulary mismatch and distractors (TC06–TC08)

**The natural weakness of TF-IDF.** TF-IDF cosine rewards exact lexical
overlap. The question asks "what procurement process applies", while the
answer lives in a terse threshold table ("At or above $100,000 but below
$121,200 … three written quotations … standard goods ITQ template …").
Because the query and the table phrase the same rule in different words, the
correct chunk's raw cosine is only **0.1362 / 0.0872 / 0.1506** for
TC06/07/08, while the value-calculation document — which *talks about*
goods purchases and dollar amounts but contains no answer — scores
**0.2865 / 0.2673 / 0.2809** and takes rank 1. In the saved Stage 2
pure-cosine diagnostic, the expected document was not in the top-3 for any
of the three cases, and the low margin (e.g. TC06 margin 0.0123) made the
Stage 3 deterministic layer abstain.

**Deterministic compensation (no learned component).** The retriever adds
two auditable signals: a **numeric-match bonus (+0.20)** when the query
amount falls inside a chunk's stated range, and a **goods/services
domain-match bonus (+0.15)** (`rag/retriever.py`). For TC06–TC08 these push
the correct chunk to rank 1 with `numeric_match = domain_match = True`; the
decision layer's **structured-evidence override** (`rag/decision.py`, Step 2)
then routes to the model even though raw cosine (0.136) is below the frozen
`TOP_SCORE_MIN`. This is a targeted fix for a measured lexical weakness, not
a semantic model — the weakness itself is inherent to TF-IDF and would
reappear on paraphrases without numbers or track words.

## 2. Two documents needed (TC21, TC22) — and where synthesis still fails

These cases are the project's central finding. A correct answer cannot come
from one chunk:

- **TC21** requires comparing the current policy with the 2019 superseded
  edition and *disclosing the supersession*. The superseded edition actually
  ranks **higher** (0.4220 vs 0.3991); margin is **0.0229 < MARGIN_MIN**.
  Pure threshold logic would abstain; the **multi-source carve-out**
  (`rag/decision.py`, Step 4 — a second source is also strong,
  ≥ `TOP_SCORE_MIN`) routes both editions to the model instead. Retrieval
  and routing succeeded; the generated answer stated the current rule but
  **did not flag the 2019 edition as superseded**.
- **TC22** requires surfacing an unreconciled contradiction between
  `13_...` (absolute gift ban) and `14_...` (conflicting guidance, which
  says so in its own text). Both were retrieved and cited; the model
  answered a bare **"No."**, silently selecting one side.

> **Core finding: the main remaining failure is no longer document
> retrieval. It is multi-evidence synthesis and disclosure — the system can
> retrieve every relevant document, including conflicting and superseded
> ones, while the generated answer still fails to surface what those
> documents jointly imply.** Grounding guarantees evidence reaches the
> model; it does not guarantee the model reports everything the evidence
> contains. See `docs/failure_analysis.md` §3.

## 3. Absent but plausible, and the threshold boundary (TC16–TC20)

Five questions ask about topics deliberately absent from the corpus
(disciplinary action, supplier appeals, supplier insurance, record
retention, FX rules). All use plausible procurement vocabulary, so lexical
hits exist — they are just not answers:

| Case | top_score (raw cosine) | margin | Deterministic layer | Final outcome |
|---|---:|---:|---|---|
| TC18 (insurance) | 0.1466 | 0.0421 | `top_score < 0.238864` → ABSTAIN | model not called |
| TC20 (FX rules) | 0.1769 | 0.0240 | `top_score < 0.238864` → ABSTAIN | model not called |
| TC16 (disciplinary) | 0.2642 | 0.0539 | passes thresholds → model called | **model itself abstains** |
| TC17 (supplier appeal) | 0.2499 | 0.1025 | passes thresholds → model called | **model itself abstains** |
| TC19 (record retention) | 0.2707 | 0.1703 | passes thresholds → model called | **model itself abstains** |

Two cases fall below the frozen threshold and are refused deterministically
with **zero model cost**; three cases are strong-looking enough to pass, and
the Foundation Model rejects them after reading the evidence — a measured
**two-line defence** against plausible-but-unsupported answers. The
trade-off this implies (where the threshold sits, what it costs) is analysed
in `docs/abstention_methodology.md` §6.
