# jev-verdict

`jev-verdict` turns semantic judgments from Jev and TypeSafe-compatible models into auditable workflow gates for automated publishing and delivery pipelines. It provides deterministic verdict caching, privacy-preserving audit ledgers without source text, per-gate failure policies, and stability measurement with zero runtime dependencies.

`jev-verdict`는 Jev 및 TypeSafe 호환 모델의 의미 기반 판정을 감사 가능한 워크플로 관문으로 변환하는 도구입니다. 원문 유출 없는 감사 원장(LLM audit ledger), 버전 연동 판정 캐시(verdict cache), 게이트별 장애 통제 정책, 반복 안정성 측정을 외부 런타임 의존성 없이 제공합니다.

## When to use this / 언제 쓰나

Use this tool if you answer **yes** to any of these questions:
- Do you need semantic policy checks before moving generated artifacts to the next step?
- Do you need an auditable trace explaining why a gate passed, warned, or blocked?
- Do you need to know if repeated runs on the exact same input produce stable scores?
- Do you need an explicit gate policy deciding whether to halt or proceed when the judgment service fails?

If none of these apply, a standard API call is sufficient and this tool is unnecessary.

다음 질문 중 하나라도 해당하면 이 도구가 적합합니다:
- 산출물을 다음 단계로 넘기기 전에 의미 기반 판단이 필요한가?
- 그 판단이 왜 그렇게 나왔는지 나중에 설명하고 감사해야 하는가?
- 같은 입력에 대한 판정이 실행마다 얼마나 흔들리는지 알아야 하는가?
- 판정 서비스 장애 시 작업을 멈출지(`stop`) 계속 갈지(`pass`) 게이트별로 정해야 하는가?

넷 중 하나라도 '예'면 이 도구가 맞습니다. 아니면 과합니다.

## 5-minute start / 5분 사용법

Requires Python 3.11+. Runtime dependencies: zero.

```bash
# 1. Install
python -m pip install -e .

# 2. Set API key (.env is also supported; keys are never stored in the ledger)
export TYPESAFE_API_KEY=your-key  # Windows: set TYPESAFE_API_KEY=your-key
# or point at one specific file:
# jev-verdict run --env-file ./keys.env --gate personal_info ...

# 3. Run a gate (pass example -> exit 0)
jev-verdict run --gate personal_info --config config/gates.example.toml --text "정부지원금 신청 기간 안내"

# Blocked example (workplace leak detected -> exit 1; 합성 예시)
jev-verdict run --gate personal_info --config config/gates.example.toml --text "저는 ○○기업 △△지점에서 근무한 담당자입니다."

# 4. Inspect audit ledger and cache (repeated identical inputs hit cache)
jev-verdict cache --stats
jev-verdict why <subject-hash>

# 5. Measure repeatability across live calls (e.g. repeat 3 -> stdev 0.0047)
jev-verdict stability --fixtures fixtures/stability.jsonl --repeat 3
```

## API key resolution / 키 우선순위

Key resolution reads **three sources only**, in this order:

1. the `TYPESAFE_API_KEY` environment variable;
2. the file given to `--env-file <path>` — that file, exactly as given;
3. `./.env` in the current working directory (no parent-directory walk), then `~/.config/jev-verdict/.env`, this tool's own configuration path.

No other location is ever read. The tool does not look into other applications' configuration directories or credential stores, and it does not scan upward from the working directory. When no key is found the command reports only that the key is unavailable; it never lists the paths it inspected. Keys are never printed and never written to the ledger.

키는 **환경변수, 사용자가 `--env-file` 로 지정한 파일, 이 도구의 설정 경로(`./.env`, `~/.config/jev-verdict/.env`)** — 이 셋만 읽습니다. 다른 프로그램의 설정·자격증명 파일은 절대 읽지 않으며, 상위 디렉터리로 올라가며 탐색하지도 않습니다. 키를 찾지 못하면 "키를 찾지 못했다"만 알리고 어디를 뒤졌는지는 출력하지 않습니다.

## Difference from jev-router

| Area | jev-router | jev-verdict |
| --- | --- | --- |
| Purpose | Changes the model selected for a prompt | Builds workflow gates from judgments |
| Cache | None | Content hash + question version + model |
| Invalidation | N/A | Question wording/type/criteria changes invalidate automatically |
| Record | None | Append-only JSONL ledger; source text is never stored |
| Policy | Hard-coded ladder | Per-gate `on_error`, `on_ambiguous`, and mode |
| Stability | None | Repeated-run variance and threshold flip rate |
| Failure | One error-pass path | Each gate chooses stop or pass |
| Audit | None | `why <subject-hash>` |

This is an independent implementation. It continues the pass-by-default design idea, not the source code.

## What this does not do / 이 도구가 하지 않는 것

- **Does not route models:** Routing prompts across model tiers belongs to `jev-router`.
- **Does not guarantee judgment accuracy:** Thresholds and criteria are set by the user.
- **Does not run bulk batches:** Validates single pipeline artifacts, not high-throughput batch tables.
- **Does not provide a web UI:** CLI and automated pipeline integration only.

- 모델을 고르지 않습니다 (모델 라우팅은 `jev-router`의 역할입니다).
- 판정 자체의 정확도를 보장하지 않습니다. 판정 기준과 문턱값은 사용자가 직접 설정합니다.
- 여러 문장을 한 번에 처리하는 대량 배치 기능은 없습니다.
- 웹 UI가 없습니다. CLI 전용입니다.

## Policy boundary / 오류 정책 경계

- **Pre-publication gate (`on_error = "stop"`):** A service failure must not silently publish unverified content.
- **Runtime hint gate (`on_error = "pass"`):** An optional advisory failure must not crash the primary pipeline.

발행 전 개인정보 관문은 서비스 장애 시에도 멈춰야 하므로 `stop`, 실행 중 보조 안내는 본 작업을 중단시키면 안 되므로 `pass`로 설정합니다. 위험 수준이 다르므로 전역 단일 오류 정책 대신 게이트별 정책을 적용합니다.

## Privacy & Ledger / 프라이버시

The ledger stores only timestamps, gate names, salted-or-unsalted subject hashes, decisions, scores, thresholds, reasons, model IDs, latency, and cache hit flags. It never stores source text or prompt bodies. Use `--ledger-salt` when unsalted hashes could permit dictionary matching.

원장에는 타임스탬프, 게이트명, 해시, 결정, 점수, 임계값, 사유, 지연시간만 기록되며 원문 텍스트는 일체 저장하지 않습니다 (검사 결과 원문 0건 저장).

## Honesty / 정직성

This tool records and measures judgments; it does not claim to improve their quality. Users must measure stability themselves with the `stability` command.

정직성 원칙: 이 저장소의 시험값은 검증기를 검증할 뿐 품질 향상을 주장하지 않는다.

## CLI & Exit codes

```bash
jev-verdict run --gate personal_info --file draft.html
jev-verdict run --gate personal_info --env-file ./keys.env --attempts 5 --file draft.html
jev-verdict check --config config/gates.example.toml --file draft.html
jev-verdict why <subject-hash>
jev-verdict stability --fixtures fixtures/stability.jsonl --repeat 3 --attempts 1
jev-verdict cache --stats
jev-verdict cache --prune
```

Exit codes: `0` pass/warn, `1` block, `2` stopped by gate error policy, `3` usage or config error. Add `--json` for machine-readable output.

## Known limitations / 알려진 한계

- **Full scans on every read:** the cache and the ledger are append-only JSONL files, and every read scans the whole file, so cost grows linearly with history (`O(n)`). Compaction is required for long-running pipelines: `jev-verdict cache --prune` rewrites the cache to one record per key, keeping the newest record per key (the newest record is what `get` uses, so this is behaviour-preserving). The ledger currently has no compaction command; it must be rotated outside the tool.
- **Single-process assumption, no file locking:** concurrent processes appending to the same cache or ledger file can interleave writes. Run one writer per file, or give each pipeline its own `--cache-file` / `--ledger` path.
- **Retry count is per gate call:** `--attempts N` (default 3) applies to each call inside one gate. HTTP 429 and 5xx responses and transient connection failures are retried with backoff; any other HTTP status stops immediately.
- **Not a quality claim:** thresholds and stability numbers describe judgments, not accuracy.
- **Score variance across runs:** Jev scores vary slightly across runs on identical inputs; use the stability command to measure variance and set thresholds.

- **매 읽기마다 전체 스캔:** 캐시와 원장은 append-only JSONL 이고 읽을 때마다 파일 전체를 훑으므로 비용이 이력에 비례해 누적됩니다(`O(n)`). 장기 운영에는 압축이 필요합니다. `jev-verdict cache --prune` 은 키별로 가장 최신 기록 하나만 남겨 캐시를 다시 씁니다(최신 기록이 조회 결과를 결정하므로 동작은 그대로입니다). 원장은 아직 압축 명령이 없어 외부에서 회전(rotation)해야 합니다.
- **파일 락 없음(단일 프로세스 전제):** 같은 캐시·원장 파일에 여러 프로세스가 동시에 append 하면 기록이 섞일 수 있습니다. 파일당 작성자를 하나로 두거나 파이프라인별로 `--cache-file` / `--ledger` 를 따로 지정하십시오.
- **재시도 수:** `--attempts N`(기본 3)은 게이트 한 번의 호출마다 적용됩니다. 재시도 대상은 HTTP 429·5xx 와 일시적 연결 실패이며, 그 외 HTTP 상태는 즉시 중단합니다.
- **실행 간 점수 변동:** Jev 점수는 같은 입력에도 실행마다 미세하게 변동하므로 이 도구의 stability 명령으로 변동을 측정해 문턱값을 정하십시오.

## Contributing & License

Issues are welcome for bug reports and discussions.

- License: MIT
- Author: lifeporterlab
