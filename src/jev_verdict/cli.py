"""Command-line interface for jev-verdict."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from .cache import VerdictCache, cache_key, questions_fingerprint
from .client import DEFAULT_MODEL, JevError, TypeSafeClient
from .gate import GateResult, apply_policy, combine
from .ledger import Ledger, subject_hash
from .stability import summarize_runs

DEFAULT_CONFIG = Path("config/gates.example.toml")
DEFAULT_CACHE = Path(".jev-verdict/cache.jsonl")
DEFAULT_LEDGER = Path(".jev-verdict/ledger.jsonl")
EXIT_CODES = {"pass": 0, "warn": 0, "block": 1, "error": 2}


def load_config(path: str | Path) -> dict[str, dict[str, Any]]:
    with Path(path).open("rb") as handle:
        data = tomllib.load(handle)
    gates = data.get("gate")
    if not isinstance(gates, dict):
        raise ValueError("config must contain [gate.<name>] tables")
    return gates


def read_subject(args: argparse.Namespace) -> str:
    if getattr(args, "text", None) is not None:
        return args.text
    if getattr(args, "file", None) is not None:
        return Path(args.file).read_text(encoding="utf-8")
    raise ValueError("one of --text or --file is required")


def execute_gate(*, text: str, gate_name: str, gate_config: dict[str, Any], cache_path: Path,
                 ledger_path: Path, ledger_salt: str, model: str = DEFAULT_MODEL,
                 use_cache: bool = True, client: TypeSafeClient | None = None) -> GateResult:
    questions = gate_config.get("question")
    question_list = questions if isinstance(questions, list) else []
    version = questions_fingerprint(question_list)
    key = cache_key(text, gate_name, version, model)
    cache = VerdictCache(cache_path)
    cached = cache.get(key, question_version=version, model=model) if use_cache and question_list else None
    if cached is not None:
        result = apply_policy(
            gate_name, gate_config, text=text, scores=cached.get("scores"),
            model_id=str(cached.get("model_id", "")), latency_ms=int(cached.get("latency_ms", 0)),
            cache_hit=True, typed_answers=cached.get("typed_answers"),
        )
    elif not text.strip() or not question_list or gate_config.get("enabled", True) is not True:
        result = apply_policy(gate_name, gate_config, text=text, scores=None)
    else:
        judge = client or TypeSafeClient()
        try:
            scores, typed_answers, model_id, latency_ms = judge.judge({"text": text}, question_list, model)
            if use_cache:
                cache.put(
                    key, question_version=version, model=model,
                    value={"scores": scores, "typed_answers": typed_answers, "model_id": model_id, "latency_ms": latency_ms},
                )
            result = apply_policy(
                gate_name, gate_config, text=text, scores=scores, model_id=model_id,
                latency_ms=latency_ms, cache_hit=False, typed_answers=typed_answers,
            )
        except JevError as exc:
            result = apply_policy(gate_name, gate_config, text=text, error=str(exc))
    Ledger(ledger_path).append({
        "gate": gate_name,
        "subject_hash": subject_hash(text, ledger_salt),
        "decision": result.decision,
        "scores": result.scores,
        "threshold": result.threshold,
        "reason": result.reason,
        "model_id": result.model_id,
        "latency_ms": result.latency_ms,
        "cache_hit": result.cache_hit,
        "ledger_salt_used": bool(ledger_salt),
    })
    return result


def _print(value: Any, *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
        return
    if isinstance(value, dict) and "decision" in value:
        print(f"decision={value['decision']}")
        if "gate" in value:
            print(f"gate={value['gate']} reason={value.get('reason', '')} cache_hit={str(value.get('cache_hit', False)).lower()}")
            if value.get("scores"):
                print("scores=" + json.dumps(value["scores"], ensure_ascii=False, sort_keys=True))
        elif "results" in value:
            for result in value["results"]:
                print(f"{result['gate']}: {result['decision']} ({result['reason']})")
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def add_io_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--cache-file", default=str(DEFAULT_CACHE))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--ledger-salt", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-verdict")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one configured gate")
    run.add_argument("--gate", required=True)
    add_io_arguments(run)

    check = sub.add_parser("check", help="run and combine every configured gate")
    add_io_arguments(check)

    why = sub.add_parser("why", help="show ledger history for a subject hash")
    why.add_argument("subject_hash")
    why.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    why.add_argument("--json", action="store_true")

    stability = sub.add_parser("stability", help="measure repeated Jev verdict variance")
    stability.add_argument("--fixtures", required=True)
    stability.add_argument("--repeat", type=int, default=5)
    stability.add_argument("--config", default=str(DEFAULT_CONFIG))
    stability.add_argument("--gate", default="personal_info")
    stability.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    stability.add_argument("--ledger-salt", default="")
    stability.add_argument("--model", default=DEFAULT_MODEL)
    stability.add_argument("--json", action="store_true")

    cache = sub.add_parser("cache", help="cache reporting")
    cache.add_argument("--stats", action="store_true", required=True)
    cache.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    cache.add_argument("--json", action="store_true")
    return parser


def command_run(args: argparse.Namespace) -> int:
    gates = load_config(args.config)
    if args.gate not in gates:
        raise ValueError(f"unknown gate: {args.gate}")
    text = read_subject(args)
    result = execute_gate(
        text=text, gate_name=args.gate, gate_config=gates[args.gate],
        cache_path=Path(args.cache_file), ledger_path=Path(args.ledger), ledger_salt=args.ledger_salt,
        model=args.model,
    )
    _print(result.to_dict(), json_mode=args.json)
    return EXIT_CODES[result.decision]


def command_check(args: argparse.Namespace) -> int:
    gates = load_config(args.config)
    text = read_subject(args)
    results = [
        execute_gate(
            text=text, gate_name=name, gate_config=config, cache_path=Path(args.cache_file),
            ledger_path=Path(args.ledger), ledger_salt=args.ledger_salt, model=args.model,
        )
        for name, config in gates.items()
    ]
    combined = combine(results)
    _print(combined, json_mode=args.json)
    return EXIT_CODES[combined["decision"]]


def command_why(args: argparse.Namespace) -> int:
    records = Ledger(args.ledger).find(args.subject_hash)
    _print({"subject_hash": args.subject_hash, "count": len(records), "records": records}, json_mode=args.json)
    return 0


def command_stability(args: argparse.Namespace) -> int:
    if args.repeat < 1:
        raise ValueError("--repeat must be at least 1")
    gates = load_config(args.config)
    rows = []
    with Path(args.fixtures).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            item = json.loads(line)
            gate_name = str(item.get("gate") or args.gate)
            if gate_name not in gates:
                raise ValueError(f"unknown gate on fixture line {line_number}: {gate_name}")
            runs = []
            for _ in range(args.repeat):
                result = execute_gate(
                    text=str(item["text"]), gate_name=gate_name, gate_config=gates[gate_name],
                    cache_path=Path(".jev-verdict/stability-unused-cache.jsonl"), ledger_path=Path(args.ledger),
                    ledger_salt=args.ledger_salt, model=args.model, use_cache=False,
                )
                runs.append(result.to_dict())
            summary = summarize_runs(runs)
            expected = item.get("expect")
            summary["expected"] = expected
            summary["expected_matches_modal"] = expected is None or summary["modal_decision"] == expected
            rows.append({
                "id": item.get("id", line_number), "gate": gate_name, "expect": expected,
                "summary": summary,
            })
    payload = {"fixtures": rows, "repeat": args.repeat}
    _print(payload, json_mode=args.json)
    has_error = any(row["summary"]["decisions"].get("error", 0) for row in rows)
    return 2 if has_error else 0


def command_cache(args: argparse.Namespace) -> int:
    stats = Ledger(args.ledger).cache_stats()
    _print(stats, json_mode=args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "run":
            return command_run(args)
        if args.command == "check":
            return command_check(args)
        if args.command == "why":
            return command_why(args)
        if args.command == "stability":
            return command_stability(args)
        if args.command == "cache":
            return command_cache(args)
    except (OSError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 3
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
