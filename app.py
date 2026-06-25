"""Multi-Agent Research Assistant — Streamlit front-end.

This module is intentionally thin: it collects a topic, wires Streamlit widgets
to :func:`research_assistant.pipeline.run_pipeline` via callbacks, and renders
the final Markdown report. All orchestration lives in the
:mod:`research_assistant` package.
"""

from __future__ import annotations

import streamlit as st

from research_assistant.agents import slugify
from research_assistant.backends import AgentResult
from research_assistant.config import MAX_TOPIC_CHARS, load_settings, sanitize_topic
from research_assistant.pipeline import (
    PipelineCallbacks,
    PipelineError,
    run_pipeline,
)


def _render_sidebar_status() -> None:
    settings = load_settings()
    st.sidebar.title("Backends")
    st.sidebar.markdown(
        f"- OpenAI key: {'configured' if settings.has_openai else 'missing'}\n"
        f"- Serper key: {'configured' if settings.has_serper else 'missing'}\n"
        f"- OpenClaw key: {'configured' if settings.has_openclaw else 'missing'}\n"
        f"- Model: `{settings.openai_model}`\n"
        f"- Max drafts: {settings.max_writer_drafts}"
    )
    st.sidebar.caption(
        "Keys are read from your local `.env` and are never displayed or logged."
    )
    st.sidebar.divider()
    st.sidebar.title("Agent traces")
    st.sidebar.caption("Raw output for each pipeline stage.")


def main() -> None:
    st.set_page_config(
        page_title="Multi-Agent Research Assistant",
        page_icon=":books:",
        layout="wide",
    )
    st.title("Multi-Agent Research Assistant")
    st.caption(
        "Researcher -> Analyst -> Writer -> Critic, orchestrated locally with "
        "OpenClaw and a GPT-4o-mini fallback."
    )

    settings = load_settings()
    _render_sidebar_status()

    topic = st.text_input(
        "Research topic",
        placeholder="e.g. The state of solid-state batteries in 2026",
        max_chars=MAX_TOPIC_CHARS,
    )
    start = st.button("Start Research", type="primary", disabled=not topic.strip())

    if not start:
        return

    # Validate before doing any work so bad input fails fast and clearly.
    try:
        topic = sanitize_topic(topic)
    except ValueError as exc:
        st.error(str(exc))
        return

    slug = slugify(topic)
    progress_box = st.container()

    def on_status(msg: str) -> None:
        progress_box.write(msg)

    def on_warning(msg: str) -> None:
        st.warning(msg)

    def on_web_results(md: str) -> None:
        with st.sidebar.expander("Live web results", expanded=False):
            st.markdown(md)

    def on_trace(stage: str, result: AgentResult) -> None:
        with st.sidebar.expander(stage, expanded=False):
            st.markdown(
                f"_Backend: `{result.backend}` · latency: {result.latency_ms} ms_"
            )
            st.code(result.content, language="markdown")

    def on_verdict(draft_idx: int, verdict: dict) -> None:
        arrow = "approved" if verdict["decision"] == "approve" else "revising"
        progress_box.write(
            f"Iteration {draft_idx}/{settings.max_writer_drafts} — "
            f"Critic score: {verdict['score']}/10 → {arrow}"
        )

    callbacks = PipelineCallbacks(
        on_status=on_status,
        on_warning=on_warning,
        on_web_results=on_web_results,
        on_trace=on_trace,
        on_verdict=on_verdict,
    )

    with st.status("Running pipeline...", expanded=True) as status:
        try:
            result = run_pipeline(topic, settings, callbacks)
        except PipelineError as exc:
            status.update(label="Pipeline failed.", state="error")
            st.error(str(exc))
            return

        status.update(
            label=(
                "Pipeline complete — report approved."
                if result.approved
                else "Pipeline complete — max revisions reached."
            ),
            state="complete",
        )

    # --- Final render + download ------------------------------------------
    if not result.approved:
        st.warning(
            "Critic did not approve within the draft budget; showing the latest "
            "draft."
        )

    if result.score_history:
        st.caption(
            "Score progression: "
            + " → ".join(f"{s}/10" for s in result.score_history)
        )

    if not result.report:
        st.error("No report was produced.")
        return

    # HTML is disabled to prevent rendering of any markup smuggled into the
    # report by upstream web content.
    st.markdown(result.report, unsafe_allow_html=False)

    st.download_button(
        label="Download report (.md)",
        data=result.report,
        file_name=f"{slug}.md",
        mime="text/markdown",
    )


if __name__ == "__main__":
    main()
