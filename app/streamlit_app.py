"""
app/streamlit_app.py
====================

STAGE 9/10 — Streamlit MVP demonstration interface for the Grounded Enterprise
Policy & Procedure Assistant.

This is a decision-support assistant, not an autonomous policy authority. It:
  * takes a procurement-policy question,
  * runs retrieval and the deterministic decision layer,
  * calls the Foundation Model only for answer-eligible cases and only when an
    API key is configured,
  * clearly distinguishes ANSWERED / NEEDS CLARIFICATION / ABSTAINED / ERROR,
  * always shows retrieved evidence and source document IDs.

Run:
    pip install -r requirements.txt streamlit
    streamlit run app/streamlit_app.py

The rest of the project runs without Streamlit; it is only needed for this UI.
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
    "ANSWERED": (
        "ANSWERED",
        "The answer below is grounded in the cited evidence.",
    ),
    "CLARIFICATION_REQUIRED": (
        "NEEDS CLARIFICATION",
        "The question is underspecified. Please provide more information.",
    ),
    "ABSTAIN": (
        "ABSTAINED",
        "The available policy evidence is insufficient to provide a grounded answer.",
    ),
    "MODEL_ERROR": (
        "ERROR",
        "The Foundation Model call failed.",
    ),
    "MODEL_OUTPUT_INVALID": (
        "ERROR",
        "The Foundation Model returned malformed output.",
    ),
}


@st.cache_resource
def get_pipeline() -> RagAnswerPipeline:
    return RagAnswerPipeline()


def main() -> None:
    st.set_page_config(
        page_title="Grounded Procurement Policy Assistant",
        page_icon=None,
        layout="wide",
    )

    st.title("Grounded Enterprise Policy & Procedure Assistant")

    st.caption(
        "Decision-support assistant for SynthCorp procurement policy questions. "
        "It is not an autonomous policy authority."
    )

    # ------------------------------------------------------------------
    # Foundation Model configuration
    # ------------------------------------------------------------------
    cfg = load_config()

    if cfg.available:
        st.success(
            f"Foundation Model configured: {cfg.model_name}. "
            "Answer-eligible questions can be generated."
        )
    else:
        st.warning(
            "No Foundation Model API key is configured. "
            "Retrieval and deterministic decision-making can still run offline, "
            "but answer generation is unavailable. "
            "Set OPENROUTER_API_KEY in the local .env file to enable "
            "Foundation Model execution."
        )

    # ------------------------------------------------------------------
    # User input
    # ------------------------------------------------------------------
    question = st.text_input(
        "Ask a procurement policy question",
        placeholder="Example: What is the procurement card per-transaction limit?",
    )

    submitted = st.button("Submit", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Please enter a procurement policy question.")
            return

        pipe = get_pipeline()

        with st.spinner("Retrieving evidence and evaluating the question..."):
            out = pipe.answer(question.strip())

        action = out.get("action", "MODEL_ERROR")

        label, note = BADGE.get(
            action,
            (action, ""),
        )

        st.subheader(label)

        if note:
            st.write(note)

        # ------------------------------------------------------------------
        # Answer
        # ------------------------------------------------------------------
        if out.get("answer"):
            st.markdown("### Answer")
            st.write(out["answer"])

        elif action == "ABSTAIN":
            st.info(
                "The system did not generate an answer because the available "
                "policy evidence was insufficient."
            )

        elif action == "CLARIFICATION_REQUIRED":
            st.info(
                "The system needs additional information before it can provide "
                "a grounded answer."
            )

        elif action in {"MODEL_ERROR", "MODEL_OUTPUT_INVALID"}:
            st.error(
                "No grounded answer is available because the Foundation Model "
                "step did not complete successfully."
            )

        # ------------------------------------------------------------------
        # Action and retrieval signals
        # ------------------------------------------------------------------
        st.markdown("### Action and retrieval signals")

        signals = out.get("signals")

        st.json(
            {
                "action": action,
                "model_status": out.get("model_status"),
                "top_source": out.get("top_source"),
                "retrieval_signals": signals,
                "thresholds": out.get("thresholds"),
            }
        )

        # ------------------------------------------------------------------
        # Citations
        # ------------------------------------------------------------------
        citations = out.get("citations", [])

        if citations:
            st.markdown("### Source documents")

            for citation in citations:
                st.write(f"- `{citation}`")

        # ------------------------------------------------------------------
        # Retrieved evidence
        # ------------------------------------------------------------------
        passages = out.get("retrieved_passages", [])

        if passages:
            st.markdown("### Retrieved evidence")

            for passage in passages:
                rank = passage.get("rank", "?")
                source = passage.get("source", "Unknown source")
                score = passage.get("score")

                if isinstance(score, float):
                    score_display = f"{score:.4f}"
                else:
                    score_display = str(score)

                with st.expander(
                    f"[{rank}] {source} - cosine similarity: {score_display}"
                ):
                    st.write(passage.get("text", ""))

        # ------------------------------------------------------------------
        # Model metadata
        # ------------------------------------------------------------------
        model_status = out.get("model_status")

        if model_status:
            st.markdown("### Foundation Model status")
            st.write(f"`{model_status}`")

    # ----------------------------------------------------------------------
    # Disclaimer
    # ----------------------------------------------------------------------
    st.divider()

    st.caption(
        "Disclaimer: This MVP returns information retrieved from a fixed set "
        "of synthetic procurement policy documents. Always verify any answer "
        "against the applicable current policy and the relevant policy owner "
        "before acting. Cosine similarity is a retrieval signal, not a confidence "
        "or probability."
    )


if __name__ == "__main__":
    main()