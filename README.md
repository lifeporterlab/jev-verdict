# jev-verdict

Auditable Jev-powered workflow gates: cache judgments, record privacy-preserving audit events, apply gate-specific policy, and measure verdict stability.

Jev 판정을 워크플로 관문으로 쓰기 위한 감사 가능한 판정 계층입니다. 판정을 캐시하고, 본문 없는 원장에 기록하고, 게이트별 정책으로 통과/경고/차단하며, 반복 실행의 흔들림을 측정합니다.

## Why / 왜 필요한가

A semantic verdict without cache identity, history, explicit failure policy, and repeatability measurements cannot be audited. `jev-verdict` keeps those concerns in ordinary Python code while Jev supplies narrow typed judgments.

캐시 키, 판정 이력, 오류 정책, 반복 안정성 수치가 없으면 의미 기반 판정을 감사할 수 없습니다. 이 프로젝트는 정책과 기록을 코드가 소유하고 Jev는 좁은 타입 판정만 제공하게 합니다.

## Difference from jev-router

| Area | jev-router | jev-verdict |
| --- | --- | --- |
| Purpose | Changes the model selected for a prompt | Builds workflow gates from judgments |
| Cache | None | Content hash + question version + model |
| Invalidation | N/A | Question wording/type/criteria changes invalidate automatically |
| Record | None | Append-only JSONL ledger; source text is never stored |
| Policy | Hard-coded ladder | Per-gate `on_error`, `on_ambiguous`, and mode |
| Stability | None | Repeated-run variance and threshold flip rate |
| Failure behavior | One error-pass path | Each gate chooses stop or pass |
| Audit command | None | `why <subject-hash>` |

This is an independent implementation. It continues the pass-by-default design idea, not the source code.

## 5-minute start / 5분 사용법

Requires Python 3.11 or newer. Runtime dependencies: zero.

1. Set the server-side key without committing it:

       set TYPESAFE_API_KEY=your-key

   Git Bash / Linux / macOS:

       export TYPESAFE_API_KEY=your-key

   A local `.env` line named `TYPESAFE_API_KEY` is also read. Its value is never printed or written to the ledger.

2. Install and run an example gate:

       python -m pip install -e .
       jev-verdict run --gate personal_info --config config/gates.example.toml --text "정부지원금 신청 기간이 다가오고 있습니다."

3. Inspect the ledger and cache:

       jev-verdict cache --stats
       jev-verdict why <subject-hash>

4. Run every configured gate:

       jev-verdict check --config config/gates.example.toml --file draft.html

5. Measure repeated behavior with live calls:

       jev-verdict stability --fixtures fixtures/stability.jsonl --repeat 5

## CLI

    jev-verdict run --gate personal_info --file draft.html
    jev-verdict run --gate personal_info --text "문장"
    jev-verdict check --config config/gates.example.toml --file draft.html
    jev-verdict why <subject-hash>
    jev-verdict stability --fixtures fixtures/stability.jsonl --repeat 5
    jev-verdict cache --stats

Add `--json` for machine-readable output. Exit codes: `0` pass/warn, `1` block, `2` stopped by a gate error policy, `3` usage/configuration error.

## Policy boundary / 오류 정책 경계

A pre-publication privacy gate should normally use `on_error = "stop"`: a service failure must not silently open the gate. A best-effort runtime hint can use `on_error = "pass"`: optional judgment failure must not kill the main request. These consequences differ, so the policies are intentionally not merged.

발행 전 개인정보 관문은 서비스 오류 때도 멈춰야 하므로 `stop`, 실행 중 보조 판단은 본 작업을 죽이면 안 되므로 `pass`가 적합합니다. 결과의 위험이 다르므로 하나의 전역 오류 정책으로 합치지 않습니다.

## Privacy

The ledger stores only timestamp, gate, salted-or-unsalted subject hash, decision, scores, threshold, reason, model id, latency, cache-hit status, and whether salt was used. It never stores source text or prompt bodies. Use `--ledger-salt` when unsalted hashes could permit dictionary matching.

Fixtures contain synthetic examples only.

## Honesty / 정직성

This tool records and measures judgments; it does not claim to improve their quality. Users must measure stability themselves with the `stability` command.

이 도구는 판정을 기록하고 측정할 뿐, 품질 향상을 주장하지 않습니다. 안정성 수치는 사용자가 `stability` 명령으로 직접 측정해야 합니다.

## Development

    python -m py_compile src/jev_verdict/*.py
    python -m pytest tests/

Live API checks require `TYPESAFE_API_KEY` and are separate from default unit tests.

## License

MIT. Copyright lifeporterlab.
