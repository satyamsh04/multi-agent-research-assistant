"""Robust parsing of the Critic agent's verdict.

The Critic is instructed to end its turn with a fenced ```json block, but LLM
output is not guaranteed to comply. This module extracts a verdict using a
layered strategy and, on total failure, returns a safe fallback verdict instead
of crashing the pipeline so a completed Writer draft is never lost.

Canonical verdict shape::

    {
        "score": int (1-10),
        "decision": "approve" | "revise",
        "unsupported_claims": list[str],
        "revision_notes": list[str],
        "parse_error": bool,           # True when the fallback was used
    }
"""

from __future__ import annotations

import json
import re
from typing import Any

FALLBACK_SCORE = 5

_FENCED_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _iter_balanced_objects(text: str):
    """Yield substrings of ``text`` that look like balanced ``{...}`` objects.

    A simple brace counter that respects double-quoted strings and escapes so
    braces inside string values do not break balancing.
    """
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    yield text[start : i + 1]
                    start = -1


def _candidate_blocks(text: str) -> list[str]:
    """Ordered list of JSON candidate strings, last-seen-first preferred later."""
    candidates: list[str] = []
    # 1) Contents of fenced code blocks (```json ... ``` or ``` ... ```).
    for fenced in _FENCED_RE.findall(text):
        candidates.append(fenced.strip())
    # 2) Any balanced { ... } object found anywhere in the raw text.
    candidates.extend(_iter_balanced_objects(text))
    return candidates


def _coerce_score(value: Any) -> int | None:
    """Best-effort coercion of a score field to an int in 1..10."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        score = int(round(value))
    elif isinstance(value, str):
        m = re.search(r"-?\d+(?:\.\d+)?", value)
        if not m:
            return None
        score = int(round(float(m.group())))
    else:
        return None
    return max(1, min(10, score))


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalise(data: dict[str, Any]) -> dict[str, Any] | None:
    """Turn a parsed dict into a canonical verdict, or None if it lacks a score."""
    score = _coerce_score(data.get("score"))
    if score is None:
        return None

    decision = data.get("decision")
    if not isinstance(decision, str) or decision.lower() not in {"approve", "revise"}:
        # Derive a decision from the score when the model omits/garbles it.
        decision = "approve" if score >= 7 else "revise"
    else:
        decision = decision.lower()

    # Keep approve/revise consistent with the score threshold.
    if score >= 7 and decision == "revise":
        # Trust the explicit revise decision but only if notes justify it;
        # otherwise the threshold wins.
        if not _as_str_list(data.get("revision_notes")):
            decision = "approve"
    if score < 7:
        decision = "revise"

    return {
        "score": score,
        "decision": decision,
        "unsupported_claims": _as_str_list(data.get("unsupported_claims")),
        "revision_notes": _as_str_list(data.get("revision_notes")),
        "parse_error": False,
    }


def fallback_verdict(reason: str) -> dict[str, Any]:
    """A safe verdict used when the Critic output cannot be parsed."""
    return {
        "score": FALLBACK_SCORE,
        "decision": "revise",
        "unsupported_claims": [],
        "revision_notes": [
            "Critic output could not be parsed as JSON; treating as a revision "
            f"request. ({reason})"
        ],
        "parse_error": True,
    }


def parse_critic_verdict(text: str) -> dict[str, Any]:
    """Extract a canonical verdict from the Critic's response.

    Never raises: if no valid verdict can be found, returns
    :func:`fallback_verdict` with ``parse_error=True`` and a default score of
    :data:`FALLBACK_SCORE`, so the pipeline can continue and the draft is kept.
    """
    if not text or not text.strip():
        return fallback_verdict("empty response")

    best: dict[str, Any] | None = None
    for block in _candidate_blocks(text):
        try:
            parsed = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        normalised = _normalise(parsed)
        if normalised is not None:
            best = normalised  # later candidates win (closest to end of output)

    if best is None:
        return fallback_verdict("no valid JSON verdict found")
    return best
