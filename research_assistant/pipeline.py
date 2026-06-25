"""UI-agnostic orchestration of the four-agent pipeline.

The pipeline runs Researcher -> Analyst -> Writer -> Critic, looping the
Writer/Critic pair until the Critic approves (score >= 7) or the draft budget
is exhausted. All progress is reported through :class:`PipelineCallbacks`, so
the same logic powers the Streamlit UI and headless tests alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .backends import AgentResult, BackendError, run_agent
from .config import Settings, sanitize_topic
from .critic import parse_critic_verdict
from .prompts import (
    build_analyst_prompt,
    build_critic_prompt,
    build_researcher_prompt,
    build_writer_prompt,
)
from .search import SearchError, format_web_results, web_search


class PipelineError(RuntimeError):
    """Raised on an unrecoverable pipeline failure."""


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


@dataclass
class PipelineCallbacks:
    """Hooks the caller (e.g. Streamlit) wires up to observe progress."""

    on_status: Callable[[str], None] = _noop
    on_warning: Callable[[str], None] = _noop
    on_web_results: Callable[[str], None] = _noop
    on_trace: Callable[[str, AgentResult], None] = _noop
    on_verdict: Callable[[int, dict[str, Any]], None] = _noop


@dataclass
class PipelineResult:
    topic: str
    report: str
    approved: bool
    score_history: list[int] = field(default_factory=list)
    final_verdict: dict[str, Any] | None = None
    drafts: int = 0


def run_pipeline(
    topic: str,
    settings: Settings,
    callbacks: PipelineCallbacks | None = None,
) -> PipelineResult:
    """Execute the full pipeline for ``topic`` and return the final report.

    Raises :class:`PipelineError` only when a stage fails irrecoverably (e.g. no
    backend available, or the Researcher/Analyst/Writer returns nothing).
    """
    cb = callbacks or PipelineCallbacks()
    topic = sanitize_topic(topic)

    def _run(agent_id: str, prompt: str, stage_label: str) -> AgentResult:
        cb.on_status(f"{stage_label} working...")
        try:
            result = run_agent(agent_id, prompt, settings)
        except BackendError as exc:
            raise PipelineError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - surface a clean message
            raise PipelineError(f"{stage_label} failed: {type(exc).__name__}.") from exc
        if not result.success or not result.content:
            raise PipelineError(f"{stage_label} returned an empty response.")
        cb.on_trace(stage_label, result)
        return result

    # --- Stage 0: live web search (best-effort) ----------------------------
    web_results: list[dict[str, str]] = []
    if settings.has_serper:
        try:
            web_results = web_search(settings.serper_api_key, topic, k=8)
        except SearchError as exc:
            cb.on_warning(
                f"Web search unavailable ({exc}). Researcher will use model "
                f"knowledge only."
            )
    else:
        cb.on_warning(
            "SERPER_API_KEY is not set. Researcher will use model knowledge "
            "only; findings may lack live URLs."
        )
    web_results_md = format_web_results(web_results)
    cb.on_web_results(web_results_md)

    # --- Stage 1: Researcher ----------------------------------------------
    researcher = _run(
        "researcher", build_researcher_prompt(topic, web_results_md), "Researcher"
    )

    # --- Stage 2: Analyst --------------------------------------------------
    analyst = _run(
        "analyst", build_analyst_prompt(topic, researcher.content), "Analyst"
    )

    # --- Stage 3 + 4: Writer / Critic revision loop ------------------------
    revision_notes: list[str] = []
    latest_draft = ""
    final_verdict: dict[str, Any] | None = None
    score_history: list[int] = []
    approved = False
    drafts = 0

    for draft_idx in range(1, settings.max_writer_drafts + 1):
        drafts = draft_idx
        writer = _run(
            "writer",
            build_writer_prompt(
                topic,
                analyst.content,
                researcher.content,
                revision_notes if draft_idx > 1 else None,
            ),
            f"Writer (draft {draft_idx})",
        )
        latest_draft = writer.content

        critic = _run(
            "critic",
            build_critic_prompt(
                topic, latest_draft, analyst.content, researcher.content
            ),
            f"Critic (review {draft_idx})",
        )

        verdict = parse_critic_verdict(critic.content)
        final_verdict = verdict
        score_history.append(int(verdict["score"]))
        cb.on_verdict(draft_idx, verdict)

        if verdict.get("parse_error"):
            cb.on_warning(
                f"Critic review {draft_idx} could not be parsed; using fallback "
                f"score {verdict['score']}."
            )

        if verdict["score"] >= 7 and verdict["decision"] == "approve":
            approved = True
            cb.on_status(
                f"Critic approved draft {draft_idx} (score {verdict['score']}/10)."
            )
            break

        revision_notes = list(verdict.get("revision_notes", []))
        cb.on_status(
            f"Critic requested revisions on draft {draft_idx} "
            f"(score {verdict['score']}/10)."
        )

    return PipelineResult(
        topic=topic,
        report=latest_draft,
        approved=approved,
        score_history=score_history,
        final_verdict=final_verdict,
        drafts=drafts,
    )
