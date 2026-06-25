"""Centralised configuration and input-validation helpers.

All environment access funnels through this module so the rest of the package
never touches :data:`os.environ` directly. Secrets are read once at import time
but never logged, echoed, or embedded in user-facing error messages.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_ROOT = PROJECT_ROOT / "agents"

# ---------------------------------------------------------------------------
# Hard limits (defence-in-depth against runaway cost / abuse)
# ---------------------------------------------------------------------------

# Maximum characters accepted for a research topic. Caps prompt size and limits
# the blast radius of prompt-injection attempts coming through the topic field.
MAX_TOPIC_CHARS = 500

# Serper "num" results are clamped into this inclusive range.
MIN_SEARCH_RESULTS = 1
MAX_SEARCH_RESULTS = 10

# The Writer/Critic revision loop is clamped into this inclusive range.
MIN_WRITER_DRAFTS = 1
MAX_WRITER_DRAFTS_CAP = 5

# Network timeouts (seconds).
SERPER_TIMEOUT_S = 20.0
OPENAI_TIMEOUT_S = 90.0


def _read_int_env(name: str, default: int, lo: int, hi: int) -> int:
    """Read an int env var, clamping to ``[lo, hi]`` and tolerating junk."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = int(raw.strip())
        except ValueError:
            value = default
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of runtime configuration.

    Instances never expose secret *values* via ``repr``; only booleans
    indicating whether a key is present are surfaced for UI/status purposes.
    """

    openai_api_key: str | None = field(repr=False, default=None)
    openclaw_api_key: str | None = field(repr=False, default=None)
    serper_api_key: str | None = field(repr=False, default=None)
    openai_model: str = "gpt-4o-mini"
    max_writer_drafts: int = 3

    # --- presence flags (safe to display) ---------------------------------
    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_openclaw(self) -> bool:
        return bool(self.openclaw_api_key)

    @property
    def has_serper(self) -> bool:
        return bool(self.serper_api_key)


def load_settings() -> Settings:
    """Build a :class:`Settings` snapshot from the current environment."""
    return Settings(
        openai_api_key=_clean(os.getenv("OPENAI_API_KEY")),
        openclaw_api_key=_clean(os.getenv("OPENCLAW_API_KEY")),
        serper_api_key=_clean(os.getenv("SERPER_API_KEY")),
        openai_model=(_clean(os.getenv("OPENAI_MODEL")) or "gpt-4o-mini"),
        max_writer_drafts=_read_int_env(
            "MAX_CRITIQUE_ITERATIONS",
            default=_read_int_env("MAX_WRITER_DRAFTS", 3, MIN_WRITER_DRAFTS, MAX_WRITER_DRAFTS_CAP),
            lo=MIN_WRITER_DRAFTS,
            hi=MAX_WRITER_DRAFTS_CAP,
        ),
    )


def _clean(value: str | None) -> str | None:
    """Strip whitespace and treat placeholder/empty values as missing."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    # Reject the obvious template placeholders shipped in .env.example so a
    # half-configured .env behaves like "not set" instead of erroring deep in
    # an API call with a confusing 401.
    if value.lower().startswith("your_") and value.lower().endswith("_here"):
        return None
    return value


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def sanitize_topic(topic: str) -> str:
    """Validate and normalise a user-supplied research topic.

    Raises :class:`ValueError` if the topic is empty or exceeds
    :data:`MAX_TOPIC_CHARS`. Control characters are stripped to avoid prompt
    smuggling via newlines/escape sequences in single-line UI inputs.
    """
    if topic is None:
        raise ValueError("Topic must not be empty.")
    # Drop control chars except normal whitespace, then collapse runs of
    # whitespace into single spaces.
    cleaned = "".join(ch for ch in topic if ch == " " or ch == "\t" or ord(ch) >= 0x20)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        raise ValueError("Topic must not be empty.")
    if len(cleaned) > MAX_TOPIC_CHARS:
        raise ValueError(
            f"Topic is too long ({len(cleaned)} chars); limit is {MAX_TOPIC_CHARS}."
        )
    return cleaned


def clamp_search_results(k: int) -> int:
    """Clamp a requested Serper result count into the allowed range."""
    try:
        k = int(k)
    except (TypeError, ValueError):
        k = MAX_SEARCH_RESULTS
    return max(MIN_SEARCH_RESULTS, min(MAX_SEARCH_RESULTS, k))
