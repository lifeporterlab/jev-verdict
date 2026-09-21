import pytest

from jev_verdict.client import JevError, parse_answers
from jev_verdict.gate import apply_policy, combine


BASE = {
    "enabled": True,
    "mode": "block",
    "on_error": "stop",
    "on_ambiguous": "pass",
    "warn_at": 0.5,
    "block_at": 0.7,
    "question": [{"id": "q", "type": "noul", "instructions": "x"}],
}


def test_pass_by_default_ladder():
    assert apply_policy("g", {**BASE, "enabled": False}, text="x", scores={"q": 1}).decision == "pass"
    assert apply_policy("g", BASE, text="x", error="offline").decision == "error"
    assert apply_policy("g", {**BASE, "on_error": "pass"}, text="x", error="offline").decision == "pass"
    assert apply_policy("g", BASE, text="", scores={"q": 1}).decision == "pass"
    assert apply_policy("g", {**BASE, "question": []}, text="x", scores={"q": 1}).decision == "pass"
    assert apply_policy("g", BASE, text="x", scores=None).decision == "pass"
    assert apply_policy("g", BASE, text="x", scores={"q": 0.2}).decision == "pass"
    assert apply_policy("g", BASE, text="x", scores={"q": 0.6}).decision == "warn"
    assert apply_policy("g", BASE, text="x", scores={"q": 0.8}).decision == "block"
    assert apply_policy("g", {**BASE, "mode": "flag"}, text="x", scores={"q": 0.8}).decision == "warn"


def test_multi_gate_composition_uses_most_consequential_result():
    passed = apply_policy("a", BASE, text="x", scores={"q": 0.1})
    blocked = apply_policy("b", BASE, text="x", scores={"q": 0.9})
    assert combine([passed, blocked])["decision"] == "block"


def test_response_validation_lowers_unknown_choice_to_other():
    questions = [{"id": "route", "type": "choice", "criteria": {"a": "A", "b": "B"}}]
    scores, typed, model = parse_answers(
        {"model": "jev-test", "answers": {"route": {"type": "choice", "choice": "not-allowed", "confidence": 0.8}}},
        questions,
    )
    assert model == "jev-test"
    assert scores == {"route": 0.8}
    assert typed["route"] == {"choice": "other", "confidence": 0.8}


def test_response_validation_rejects_nonfinite_or_out_of_range_scores():
    questions = [{"id": "q", "type": "noul"}]
    with pytest.raises(JevError):
        parse_answers({"model": "jev-test", "answers": {"q": {"type": "noul", "noul": float("nan")}}}, questions)
    with pytest.raises(JevError):
        parse_answers({"model": "jev-test", "answers": {"q": {"type": "noul", "noul": 1.1}}}, questions)
