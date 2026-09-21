"""Append-only JSONL audit ledger that never stores source text."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ALLOWED_FIELDS = {
    "ts", "gate", "subject_hash", "decision", "scores", "threshold", "reason",
    "model_id", "latency_ms", "cache_hit", "ledger_salt_used",
}


def subject_hash(text: str, salt: str = "") -> str:
    return hashlib.sha256((salt + text).encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        extra = set(record) - _ALLOWED_FIELDS
        if extra:
            raise ValueError(f"unsupported ledger fields: {sorted(extra)}")
        saved = dict(record)
        saved.setdefault("ts", datetime.now(timezone.utc).isoformat())
        missing = _ALLOWED_FIELDS - set(saved)
        if missing:
            raise ValueError(f"missing ledger fields: {sorted(missing)}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(saved, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        return saved

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        found: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    found.append(record)
        return found

    def find(self, hash_value: str) -> list[dict[str, Any]]:
        return [record for record in self.records() if record.get("subject_hash") == hash_value]

    def cache_stats(self) -> dict[str, int | float]:
        records = self.records()
        hits = sum(1 for record in records if record.get("cache_hit") is True)
        total = len(records)
        return {"lookups": total, "hits": hits, "misses": total - hits, "hit_rate": hits / total if total else 0.0}
