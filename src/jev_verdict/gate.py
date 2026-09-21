"""Gate policy, pass-by-default ladder, and multi-gate composition."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GateResult:
    gate: str
    decision: str
    scores: dict[str, float]
    threshold: float
    reason: str
    model_id: str = ""
    latency_ms: int = 0
    cache_hit: bool = False
    typed_answers: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_policy(gate_name: str, config: dict[str, Any] | None, *, text: str,
                 scores: dict[str, float] | None = None, error: str = "",
                 model_id: str = "", latency_ms: int = 0, cache_hit: bool = False,
                 typed_answers: dict[str, Any] | None = None) -> GateResult:
    gate = config or {}
    threshold = float(gate.get("block_at", 1.0))
    if gate.get("enabled", True) is not True:
        return GateResult(gate_name, "pass", {}, threshold, "gate disabled", model_id, latency_ms, cache_hit, typed_answers)
    if error:
        if gate.get("on_error", "pass") == "stop":
            return GateResult(gate_name, "error", {}, threshold, error, model_id, latency_ms, cache_hit, typed_answers)
        return GateResult(gate_name, "pass", {}, threshold, f"error-pass: {error}", model_id, latency_ms, cache_hit, typed_answers)
    if not text.strip():
        return GateResult(gate_name, "pass", {}, threshold, "empty input", model_id, latency_ms, cache_hit, typed_answers)
    questions = gate.get("question")
    if not isinstance(questions, list) or not questions:
        return GateResult(gate_name, "pass", {}, threshold, "no questions", model_id, latency_ms, cache_hit, typed_answers)
    if not scores:
        return GateResult(gate_name, "pass", {}, threshold, "no verdict", model_id, latency_ms, cache_hit, typed_answers)
    peak = max(scores.values())
    if peak < threshold:
        warn_at = gate.get("warn_at")
        if warn_at is not None and peak >= float(warn_at):
            return GateResult(gate_name, "warn", scores, float(warn_at), "warning threshold reached", model_id, latency_ms, cache_hit, typed_answers)
        ambiguous = str(gate.get("on_ambiguous", "pass"))
        decision = ambiguous if ambiguous in {"pass", "warn", "block"} else "pass"
        return GateResult(gate_name, decision, scores, threshold, "below block threshold", model_id, latency_ms, cache_hit, typed_answers)
    decision = "warn" if gate.get("mode", "block") == "flag" else "block"
    return GateResult(gate_name, decision, scores, threshold, "block threshold reached", model_id, latency_ms, cache_hit, typed_answers)


def combine(results: list[GateResult]) -> dict[str, Any]:
    rank = {"pass": 0, "warn": 1, "block": 2, "error": 3}
    decision = max((item.decision for item in results), key=lambda item: rank[item], default="pass")
    return {"decision": decision, "results": [item.to_dict() for item in results]}
