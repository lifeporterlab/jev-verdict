# Design

## Goal

`jev-verdict` is an auditable decision layer between semantic judgments and workflow actions. Jev answers typed questions; deterministic Python owns identity, caching, policy, audit history, and statistics.

## Novelty relative to jev-router

The predecessor routes a prompt to a model and therefore optimizes for non-disruptive request forwarding. This project does not select a model. It turns one or more judgments into explicit workflow gates.

New elements are:

1. A cache identity derived from normalized content, gate name, normalized question-definition fingerprint, and requested model.
2. Automatic invalidation when question text, type, or criteria changes.
3. An append-only audit ledger that excludes source text.
4. Per-gate failure policy instead of one global error-pass behavior.
5. Repeated-run statistics, including population standard deviation and threshold flip rate.
6. A `why` command that retrieves all events for a subject hash.

No source code was copied from jev-router. The inherited design idea is the conservative pass-by-default ladder: consequential behavior happens only after every prerequisite is satisfied.

## Pass-by-default ladder

Evaluation order is intentional:

1. Disabled gate: pass.
2. Error: apply this gate's `on_error` policy.
3. Empty input: pass.
4. No questions: pass.
5. No verdict: pass.
6. Question-version mismatch: cache miss, then obtain a fresh verdict; stale values are never used.
7. Below the block threshold: apply warning threshold and `on_ambiguous` policy.
8. Otherwise: block, or warn when the gate is in `flag` mode.

For gates with several Noul questions, policy uses the maximum score. This is an "any serious violation" rule: one strongly positive privacy dimension is enough to close the gate, and unrelated low scores cannot average it away.

## Why error policies remain separate

A pre-publication privacy gate protects an irreversible external action. If Jev is unavailable, `on_error = "stop"` preserves the safety boundary. A best-effort runtime classifier is advisory; `on_error = "pass"` preserves availability. Merging these into one global behavior would silently choose either unsafe publication or unnecessary runtime outages.

## Cache

    questions_fingerprint = sha256(canonical(question id, type, instructions, criteria))
    key = sha256(normalized_text || gate_name || questions_fingerprint || model)

`.jev-verdict/cache.jsonl` is append-only. Readers scan newest to oldest, and the latest valid matching record wins. The key and stored metadata both bind the record to the question fingerprint and model.

## Ledger and privacy

`.jev-verdict/ledger.jsonl` is append-only. Its strict allow-list is:

- `ts`
- `gate`
- `subject_hash`
- `decision`
- `scores`
- `threshold`
- `reason`
- `model_id`
- `latency_ms`
- `cache_hit`
- `ledger_salt_used`

`subject_hash = sha256(salt + text)`. The source text and outbound request body are never ledger fields. Salt is optional for compatibility, but recommended where dictionary attacks are plausible.

## Response validation

The response must be an object with an `answers` object and a non-empty model id. Every configured answer must be present and match its declared type. Probabilities must be finite and within `[0, 1]`. Unknown Choice values are lowered to `other`; invalid numeric values and malformed structures become errors and are resolved by each gate's `on_error` policy.

## Key resolution

The key is a credential, so the resolution order is deliberately narrow and fully enumerable:

1. the `TYPESAFE_API_KEY` environment variable;
2. the file named by `--env-file`, used exactly as given and only if non-empty;
3. `./.env` in the current working directory, then `~/.config/jev-verdict/.env` (this tool's own config path).

Nothing else on the machine is consulted: no parent-directory walk, and no other application's configuration or credential store. `key_source_candidates()` returns that list in priority order so the guarantee is unit-testable rather than asserted in prose. Only the `TYPESAFE_API_KEY` name is honoured inside a file; other names are ignored. A miss returns an empty string, and the failure message names no inspected paths.

## Constants and retries

`attempts` (default 3, CLI `--attempts N`) counts attempts per gate call. HTTP 429 and 5xx responses are retried because they are transient by definition, and transport failures (connection errors, timeouts, unparsable bodies) are retried up to the same limit with exponential backoff (`0.5 * 2**attempt`). Any other HTTP status is terminal for that call and is handed to the gate's `on_error` policy. The endpoint and model defaults are not configurable through the environment.

## Known limitations

- **Linear scans:** both `.jev-verdict/cache.jsonl` and `.jev-verdict/ledger.jsonl` are append-only and fully read on every access, so read cost grows with history. `cache --prune` compacts the cache to one record per key (the newest, which is the record `get` would use, so lookups are unchanged). The ledger has no compaction command.
- **No file locking:** the append path assumes a single writer per file. Concurrent processes can interleave lines; separate `--cache-file` and `--ledger` paths per pipeline are the supported answer.
- **Statistics describe judgments, not accuracy:** stability reports variance around the configured threshold and says nothing about correctness.

## Stability

For each fixed synthetic fixture, caching is disabled and Jev is called N times. The command reports per-question mean, population standard deviation, minimum, and maximum. It also finds the modal final decision and reports:

    threshold_flip_rate = runs whose decision differs from modal decision / all runs

This measures instability around the configured policy boundary. It does not prove accuracy or quality.

## Non-claims

This tool records and measures judgments. It does not claim that Jev, the gate, or the chosen thresholds improve quality. Thresholds must be evaluated on the user's own representative data.
