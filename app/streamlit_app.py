"""
app/streamlit_app.py
====================

STAGE 9/10 — Streamlit MVP demonstration interface for the Grounded Enterprise
Policy & Procedure Assistant.

This is a decision-SUPPORT assistant, not an autonomous policy authority. It:
  * takes a procurement-policy question,
  * runs retrieval + the deterministic decision layer (offline),
  * calls the Foundation Model ONLY for answer-eligible cases AND only when an
    API key is configured; otherwise it shows PENDING EXECUTION (never a fake
    answer),
  * clearly distinguishes ANSWERED / NEEDS CLARIFICATION / ABSTAINED /
    PENDING EXECUTION / ERROR,
  * always shows retrieved evidence and source document IDs.

Run:
    pip install -r requirements.txt streamlit
    streamlit run app/streamlit_app.py

(The rest of the project runs without Streamlit; it is only needed for this UI.)
"""

from __future__ import annotations

import os
import sys

import streamlit as st

# Make the rag package importable.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "rag"))

from rag_answer import RagAnswerPipeline  # noqa: E402
from model_client import load_config  # noqa: E402


BADGE = {
    "ANSWERED": ("✅ ANSWERED", "The answer below is grounded in the cited evidence."),
    "CLARIFICATION_REQUIRED": ("🟡 NEEDS CLARIFICATION", "The question is underspecified."),
    "ABSTAIN": ("⛔ ABSTAINED", "Insufficient evidence in the policy corpus."),
    "PENDING_EXECUTION": ("⏳ PENDING EXECUTION", "No API key configured — the model step was not run."),
    "MODEL_ERROR": ("⚠️ ERROR", "The model call failed."),
    "MODEL_OUTPUT_INVALID": ("⚠️ ERROR", "The model returned malformed output."),
}


@st.cache_resource
def get_pipeline() -> RagAnswerPipeline:
    return RagAnswerPipeline()


def main() -> None:
    st.set_page_config(page_title="Grounded Procurement Policy Assistant",
                       page_icon="📄")
    st.title("📄 Grounded Enterprise Policy & Procedure Assistant")
    st.caption(
        "Decision-support assistant for SynthCorp procurement policy questions. "
        "It is **not** an autonomous policy authority."
    )

    cfg = load_config()
    if cfg.available:
        st.success(f"Foundation Model configured: `{cfg.model_name}` (answers will be generated).")
    else:
        st.warning(
            "No API key configured. Retrieval + the deterministic decision layer "
            "run offline. Answer-eligible questions are shown as **PENDING "
            "EXECUTION** — no answer is fabricated. Set `OPENROUTER_API_KEY` in a "
            "`.env` file to enable answers."
        )

    question = st.text_input(
        "Ask a procurement policy question",
        placeholder="e.g. What is the procurement card per-transaction limit?",
    )
    submitted = st.button("Submit", type="primary")

    if submitted and question.strip():
        pipe = get_pipeline()
        with st.spinner("Retrieving evidence and deciding..."):
            out = pipe.answer(question.strip())

        action = out["action"]
        label, note = BADGE.get(action, (f"❓ {action}", ""))
        st.subheader(label)
        if note:
            st.write(note)

        # Answer / message
        if out.get("answer"):
            st.markdown("### Answer")
            st.write(out["answer"])
        elif action == "PENDING_EXECUTION":
            st.info(
                "This question is answer-eligible: relevant evidence was found. "
                "An answer will be generated once a Foundation Model API key is "
                "configured. No answer is shown because none has been generated."
            )

        # Action + signals
        st.markdown("### Action & signals")
        st.write({
            "action": action,
            "model_status": out.get("model_status"),
            "top_source": out.get("top_source"),
            "retrieval_signals": out.get("signals"),
            "thresholds": out.get("thresholds"),
        })

        # Citations
        if out.get("citations"):
            st.markdown("### Source documents (citations)")
            for c in out["citations"]:
                st.write(f"- `{c}`")

        # Evidence
        passages = out.get("retrieved_passages", [])
        if passages:
            st.markdown("### Retrieved evidence")
            for p in passages:
                with st.expander(f"[{p['rank']}] {p['source']} (cosine={p['score']})"):
                    st.write(p["text"])

    st.divider()
    st.caption(
        "⚠️ Disclaimer: This MVP returns information retrieved from a fixed set of "
        "**synthetic** procurement policy documents. Always verify any answer "
        "against the applicable current policy and the relevant policy owner "
        "before acting. Cosine similarity is a retrieval signal, not a confidence "
        "or probability."
    )


if __name__ == "__main__":
    main()
