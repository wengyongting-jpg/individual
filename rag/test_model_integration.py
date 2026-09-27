"""
rag/test_model_integration.py
=============================

STAGE 6 — Unit tests for the Foundation Model integration path.

These are UNIT TESTS of parsing / routing / error handling. They use a fake
model client to exercise code paths deterministically. They are NOT an
evaluation and NEVER present mocked output as a real model result: the real
evaluation (evaluation/run_rag.py) marks un-executed model steps as
PENDING_EXECUTION.

Covered cases:
  * missing API key            -> PENDING_EXECUTION
  * valid structured response  -> ANSWERED parsed + validated
  * invalid JSON               -> MODEL_OUTPUT_INVALID
  * fenced JSON (```json ...)  -> parsed OK
  * model refusal / abstain    -> ABSTAIN respected
  * timeout / API error        -> MODEL_ERROR
  * deterministic ABSTAIN/CLARIFY never calls the model

Run:
    python rag/test_model_integration.py
"""

from __future__ import annotations

import sys

from model_client import ModelResult, ModelConfig
from prompt import parse_and_validate, OutputValidationError
from rag_answer import RagAnswerPipeline


class FakeClient:
    """Stand-in ModelClient that returns a scripted ModelResult."""
    def __init__(self, result: ModelResult):
        self._result = result
        self.calls = 0

    def complete(self, messages, max_tokens: int = 600) -> ModelResult:
        self.calls += 1
        return self._result


PASS, FAIL = "PASS", "FAIL"
_results = []


def check(name: str, condition: bool) -> None:
    _results.append((name, PASS if condition else FAIL))
    print(f"  [{PASS if condition else FAIL}] {name}")


def test_missing_key_is_pending():
    # A client whose config has no key returns PENDING_EXECUTION.
    from model_client import ModelClient
    client = ModelClient(ModelConfig(api_key=None, model_name="m",
                                     base_url="u", temperature=0.0))
    res = client.complete([{"role": "user", "content": "x"}])
    check("missing API key -> PENDING_EXECUTION", res.status == "PENDING_EXECUTION")


def test_valid_response_answered():
    raw = ('{"action":"ANSWERED","answer":"$5,000 per transaction.",'
           '"evidence":[{"source":"09_procurement_card_policy.txt","text":"...$5,000..."}],'
           '"citations":["09_procurement_card_policy.txt"],"confidence":"high"}')
    pipe = RagAnswerPipeline(model_client=FakeClient(
        ModelResult(status="OK", raw_text=raw, latency_ms=12.0)))
    out = pipe.answer("What is the procurement card per-transaction limit?")
    check("valid model response -> ANSWERED", out["action"] == "ANSWERED")
    check("valid response keeps citations", out["citations"] == ["09_procurement_card_policy.txt"])


def test_invalid_json():
    pipe = RagAnswerPipeline(model_client=FakeClient(
        ModelResult(status="OK", raw_text="not json at all", latency_ms=5.0)))
    out = pipe.answer("What is the procurement card per-transaction limit?")
    check("invalid JSON -> MODEL_OUTPUT_INVALID", out["action"] == "MODEL_OUTPUT_INVALID")


def test_fenced_json():
    raw = ('```json\n{"action":"ANSWERED","answer":"ok",'
           '"evidence":[],"citations":[],"confidence":"low"}\n```')
    parsed = parse_and_validate(raw)
    check("fenced JSON parses", parsed["action"] == "ANSWERED")


def test_model_refusal_abstain():
    raw = ('{"action":"ABSTAIN","answer":"Insufficient evidence was found in the '
           'available procurement policies to answer this question reliably. '
           'Please verify with the relevant policy owner.",'
           '"evidence":[],"citations":[],"confidence":"low"}')
    pipe = RagAnswerPipeline(model_client=FakeClient(
        ModelResult(status="OK", raw_text=raw, latency_ms=8.0)))
    out = pipe.answer("What is the procurement card per-transaction limit?")
    check("model refusal/abstain respected", out["action"] == "ABSTAIN")


def test_timeout_error():
    pipe = RagAnswerPipeline(model_client=FakeClient(
        ModelResult(status="ERROR", error="TimeoutError: timed out", latency_ms=60000.0)))
    out = pipe.answer("What is the procurement card per-transaction limit?")
    check("timeout/API error -> MODEL_ERROR", out["action"] == "MODEL_ERROR")


def test_deterministic_paths_never_call_model():
    fake = FakeClient(ModelResult(status="OK", raw_text="{}", latency_ms=1.0))
    pipe = RagAnswerPipeline(model_client=fake)
    pipe.answer("Who signs off on a $50,000 purchase?")      # clarification
    pipe.answer("What is the policy on employee travel reimbursement?")  # abstain
    check("deterministic ABSTAIN/CLARIFY do not call the model", fake.calls == 0)


def test_invalid_abstain_with_evidence_rejected():
    bad = '{"action":"ABSTAIN","answer":"x","evidence":[{"source":"a"}],"citations":[]}'
    try:
        parse_and_validate(bad)
        check("ABSTAIN-with-evidence rejected", False)
    except OutputValidationError:
        check("ABSTAIN-with-evidence rejected", True)


def main():
    print("Model integration unit tests (fake client; not an evaluation):")
    test_missing_key_is_pending()
    test_valid_response_answered()
    test_invalid_json()
    test_fenced_json()
    test_model_refusal_abstain()
    test_timeout_error()
    test_deterministic_paths_never_call_model()
    test_invalid_abstain_with_evidence_rejected()
    failed = [n for n, s in _results if s == FAIL]
    print(f"\n{len(_results) - len(failed)}/{len(_results)} passed")
    if failed:
        print("FAILED:", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
