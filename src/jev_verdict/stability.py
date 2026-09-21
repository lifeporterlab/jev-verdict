"""Repeated-run stability statistics."""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {"repeat": 0, "questions": {}, "decisions": {}, "modal_decision": None, "threshold_flip_rate": 0.0}
    question_ids = sorted({qid for run in runs for qid in run.get("scores", {})})
    questions: dict[str, Any] = {}
    for qid in question_ids:
        values = [float(run["scores"][qid]) for run in runs if qid in run.get("scores", {})]
        questions[qid] = {
            "mean": statistics.fmean(values),
            "stdev": statistics.pstdev(values),
            "min": min(values),
            "max": max(values),
        }
    decisions = Counter(str(run.get("decision", "error")) for run in runs)
    modal = decisions.most_common(1)[0][0]
    flips = sum(1 for run in runs if str(run.get("decision", "error")) != modal)
    return {
        "repeat": len(runs),
        "questions": questions,
        "decisions": dict(decisions),
        "modal_decision": modal,
        "threshold_flip_rate": flips / len(runs),
    }
