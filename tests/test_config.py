"""Tests for input validation and config helpers (no network required)."""

from __future__ import annotations

import pytest

from research_assistant.config import (
    MAX_SEARCH_RESULTS,
    MAX_TOPIC_CHARS,
    clamp_search_results,
    sanitize_topic,
)


def test_sanitize_collapses_whitespace():
    assert sanitize_topic("  solid   state\tbatteries  ") == "solid state batteries"


def test_sanitize_strips_control_characters():
    assert sanitize_topic("hello\x00\x07world") == "helloworld"


def test_sanitize_rejects_empty():
    with pytest.raises(ValueError):
        sanitize_topic("   ")


def test_sanitize_rejects_overlong():
    with pytest.raises(ValueError):
        sanitize_topic("x" * (MAX_TOPIC_CHARS + 1))


def test_clamp_search_results_bounds():
    assert clamp_search_results(0) == 1
    assert clamp_search_results(999) == MAX_SEARCH_RESULTS
    assert clamp_search_results("bad") == MAX_SEARCH_RESULTS
    assert clamp_search_results(5) == 5
