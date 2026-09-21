"""Append-only verdict cache; latest valid record wins."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .text import normalize_text


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def questions_fingerprint(questions: Iterable[dict[str, Any]]) -> str:
    normalized = [
        {
            "id": str(q.get("id", "")),
            "type": str(q.get("type", "")),
            "instructions": normalize_text(str(q.get("instructions", ""))),
            "criteria": q.get("criteria"),
        }
        for q in questions
    ]
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def cache_key(text: str, gate_name: str, question_version: str, model: str) -> str:
    material = "\0".join((normalize_text(text), gate_name, question_version, model))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class VerdictCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    records.append(value)
        return records

    def get(self, key: str, *, question_version: str, model: str) -> dict[str, Any] | None:
        for record in reversed(self._records()):
            if record.get("key") != key:
                continue
            if record.get("question_version") != question_version or record.get("model") != model:
                return None
            value = record.get("value")
            return value if isinstance(value, dict) else None
        return None

    def put(self, key: str, *, question_version: str, model: str, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"key": key, "question_version": question_version, "model": model, "value": value}
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(record) + "\n")

    def stats(self) -> dict[str, int | float]:
        records = self._records()
        keys = {str(record.get("key")) for record in records if record.get("key")}
        hits = sum(int(bool(record.get("cache_hit"))) for record in records)
        lookups = sum(int(record.get("lookups", 0)) for record in records)
        return {
            "records": len(records),
            "unique_keys": len(keys),
            "hits": hits,
            "lookups": lookups,
            "hit_rate": (hits / lookups) if lookups else 0.0,
        }
