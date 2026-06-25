"""Agent persona loading (OpenClaw-style SOUL.md + SKILL.md bootstrap).

Prompts are read from disk on every call (no caching) so edits to a SOUL or
SKILL file take effect on the next pipeline run without restarting the app.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import AGENTS_ROOT

# Map agent id -> (soul filename, skill filename) relative to the agent dir.
AGENT_FILES: dict[str, tuple[str, str]] = {
    "researcher": ("SOUL.md", "skills/research.SKILL.md"),
    "analyst": ("SOUL.md", "skills/analyse.SKILL.md"),
    "writer": ("SOUL.md", "skills/write_report.SKILL.md"),
    "critic": ("SOUL.md", "skills/validate.SKILL.md"),
}


class AgentDefinitionError(RuntimeError):
    """Raised when an agent's SOUL/SKILL files are missing or unreadable."""


def _safe_read(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise AgentDefinitionError(f"Missing agent definition file: {path.name}") from exc
    except OSError as exc:
        raise AgentDefinitionError(f"Could not read agent file {path.name}: {exc}") from exc
    if not text.strip():
        raise AgentDefinitionError(f"Agent definition file is empty: {path.name}")
    return text


def load_agent_prompt(agent_id: str) -> str:
    """Return the combined SOUL + SKILL text used as a system prompt.

    Raises :class:`AgentDefinitionError` (a ``RuntimeError`` subclass) if the
    agent id is unknown or its files cannot be read.
    """
    if agent_id not in AGENT_FILES:
        raise AgentDefinitionError(f"Unknown agent id: {agent_id!r}")

    soul_name, skill_name = AGENT_FILES[agent_id]
    agent_dir = AGENTS_ROOT / agent_id
    soul_text = _safe_read(agent_dir / soul_name)
    skill_text = _safe_read(agent_dir / skill_name)
    return f"# SOUL\n\n{soul_text}\n\n---\n\n# SKILL\n\n{skill_text}\n"


def slugify(value: str) -> str:
    """Filesystem-safe slug for download filenames."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "report"
