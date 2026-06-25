"""Multi-Agent Research Assistant — core package.

A four-stage pipeline (Researcher -> Analyst -> Writer -> Critic) that turns a
topic into a fact-checked Markdown report. Agent personas are bootstrapped from
``agents/<name>/SOUL.md`` + ``agents/<name>/skills/*.SKILL.md`` and executed via
the OpenClaw gateway when available, falling back transparently to OpenAI.

The package is intentionally UI-agnostic: :mod:`research_assistant.pipeline`
exposes :func:`run_pipeline`, which the Streamlit front-end in ``app.py`` drives
through a small set of callbacks. This separation keeps the orchestration logic
testable without a running Streamlit server.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
