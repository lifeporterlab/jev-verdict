"""Minimal stdlib TypeSafe System One HTTP client."""

from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"


class JevError(RuntimeError):
    pass


def load_api_key() -> str:
    value = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if value:
        return value
    candidates = [Path.cwd() / ".env"]
    candidates.extend(parent / ".env" for parent in Path.cwd().parents)
    candidates.extend([
        Path.home() / ".env",
        Path.home() / "AppData" / "Local" / "hermes" / ".env",
        Path.home() / "AppData" / "Local" / "hermes" / "cache" / "scratch" / ".env",
        Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "developer" / ".env",
    ])
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, raw = stripped.split("=", 1)
            if name.strip() == "TYPESAFE_API_KEY":
                return raw.strip().strip("\"'")
    return ""


def build_payload(state: Any, questions: list[dict[str, Any]], model: str = DEFAULT_MODEL) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for question in questions:
        qid = str(question.get("id", "")).strip()
        if not qid:
            raise JevError("question id is required")
        item = {key: value for key, value in question.items() if key != "id"}
        mapped[qid] = item
    return {"state": state, "model": model, "questions": mapped}


def _finite_probability(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise JevError(f"{label} must be numeric") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise JevError(f"{label} must be between 0 and 1")
    return number


def parse_answers(response: Any, questions: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, Any], str]:
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise JevError("response.answers must be an object")
    answers = response["answers"]
    scores: dict[str, float] = {}
    typed: dict[str, Any] = {}
    for question in questions:
        qid = str(question["id"])
        qtype = str(question.get("type", ""))
        answer = answers.get(qid)
        if not isinstance(answer, dict):
            raise JevError(f"missing or invalid answer: {qid}")
        if answer.get("type") != qtype:
            raise JevError(f"answer type mismatch: {qid}")
        if qtype == "noul":
            score = _finite_probability(answer.get("noul"), f"{qid}.noul")
            scores[qid] = score
            typed[qid] = score
        elif qtype == "choice":
            allowed = set((question.get("criteria") or {}).keys())
            choice = str(answer.get("choice", "other"))
            if choice not in allowed:
                choice = "other"
            confidence = _finite_probability(answer.get("confidence", 0.0), f"{qid}.confidence")
            scores[qid] = confidence
            typed[qid] = {"choice": choice, "confidence": confidence}
        elif qtype == "score":
            raw_score = answer.get("score")
            score = _finite_probability(raw_score, f"{qid}.score")
            scores[qid] = score
            typed[qid] = score
        else:
            raise JevError(f"unsupported question type: {qtype}")
    model_id = str(response.get("model") or "")
    if not model_id:
        raise JevError("response.model is required")
    return scores, typed, model_id


class TypeSafeClient:
    def __init__(self, *, api_key: str = "", endpoint: str = DEFAULT_ENDPOINT, timeout: float = 15.0,
                 attempts: int = 3, sleeper: Callable[[float], None] = time.sleep):
        self.api_key = api_key or load_api_key()
        self.endpoint = endpoint
        self.timeout = timeout
        self.attempts = attempts
        self.sleeper = sleeper

    def judge(self, state: Any, questions: list[dict[str, Any]], model: str = DEFAULT_MODEL) -> tuple[dict[str, float], dict[str, Any], str, int]:
        if not self.api_key:
            raise JevError("TYPESAFE_API_KEY is unavailable")
        payload = build_payload(state, questions, model)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            request = urllib.request.Request(
                self.endpoint,
                data=body,
                method="POST",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            )
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                latency_ms = round((time.perf_counter() - started) * 1000)
                scores, typed, model_id = parse_answers(parsed, questions)
                return scores, typed, model_id, latency_ms
            except urllib.error.HTTPError as exc:
                last_error = exc
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if not retryable or attempt + 1 >= self.attempts:
                    raise JevError(f"TypeSafe HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last_error = exc
                if attempt + 1 >= self.attempts:
                    raise JevError("TypeSafe request failed") from exc
            self.sleeper(0.5 * (2 ** attempt))
        raise JevError("TypeSafe request failed") from last_error
