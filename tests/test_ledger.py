import json

import pytest

from jev_verdict.ledger import Ledger, subject_hash


def record(hash_value):
    return {
        "gate": "privacy", "subject_hash": hash_value, "decision": "pass", "scores": {"q": 0.1},
        "threshold": 0.7, "reason": "below block threshold", "model_id": "jev-test", "latency_ms": 4,
        "cache_hit": False, "ledger_salt_used": True,
    }


def test_ledger_is_append_only_and_contains_no_source_text(tmp_path):
    text = "synthetic secret sentence"
    ledger = Ledger(tmp_path / "ledger.jsonl")
    hash_value = subject_hash(text, "salt")
    ledger.append(record(hash_value))
    ledger.append({**record(hash_value), "decision": "block"})
    assert len(ledger.find(hash_value)) == 2
    raw = ledger.path.read_text(encoding="utf-8")
    assert text not in raw
    assert '"salt"' not in raw
    assert all("text" not in item and "salt" not in item for item in map(json.loads, raw.splitlines()))


def test_ledger_rejects_unapproved_fields(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError):
        ledger.append({**record("abc"), "text": "must not be stored"})
