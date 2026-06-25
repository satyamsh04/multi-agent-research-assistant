"""Tests for the robust Critic verdict parser (no network required)."""

from __future__ import annotations

from research_assistant.critic import FALLBACK_SCORE, parse_critic_verdict


def test_clean_fenced_json_approve():
    text = """Looks solid.
```json
{"score": 8, "decision": "approve", "unsupported_claims": [], "revision_notes": []}
```"""
    v = parse_critic_verdict(text)
    assert v["score"] == 8
    assert v["decision"] == "approve"
    assert v["parse_error"] is False


def test_bare_json_without_fence():
    text = '{"score": 6, "decision": "revise", "revision_notes": ["Expand summary"]}'
    v = parse_critic_verdict(text)
    assert v["score"] == 6
    assert v["decision"] == "revise"
    assert v["revision_notes"] == ["Expand summary"]


def test_prose_then_json_picks_last_valid_object():
    text = """Some {not json} noise here.
And a code block:
```json
{"score": 9, "decision": "approve", "unsupported_claims": [], "revision_notes": []}
```"""
    v = parse_critic_verdict(text)
    assert v["score"] == 9
    assert v["decision"] == "approve"


def test_nested_braces_in_string_value_do_not_break_parsing():
    text = (
        '{"score": 7, "decision": "approve", "unsupported_claims": '
        '["contains a { brace } in text"], "revision_notes": []}'
    )
    v = parse_critic_verdict(text)
    assert v["score"] == 7
    assert v["unsupported_claims"] == ["contains a { brace } in text"]


def test_score_decision_mismatch_is_corrected_to_revise():
    text = '{"score": 4, "decision": "approve", "revision_notes": []}'
    v = parse_critic_verdict(text)
    assert v["score"] == 4
    assert v["decision"] == "revise"  # score < 7 always forces revise


def test_float_score_is_coerced_and_clamped():
    text = '{"score": 12.6, "decision": "approve"}'
    v = parse_critic_verdict(text)
    assert v["score"] == 10  # clamped to 1..10


def test_malformed_output_returns_safe_fallback():
    v = parse_critic_verdict("the critic forgot to emit json")
    assert v["parse_error"] is True
    assert v["score"] == FALLBACK_SCORE
    assert v["decision"] == "revise"
    assert v["revision_notes"]  # non-empty explanation


def test_empty_output_returns_fallback():
    v = parse_critic_verdict("")
    assert v["parse_error"] is True
    assert v["score"] == FALLBACK_SCORE
