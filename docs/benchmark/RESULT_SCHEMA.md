# Result Schema

Defined in `src/voiceos/benchmark/results.py` (`BenchmarkResult`, pydantic, unknown keys
rejected). Schema id: `voiceos.benchmark.result/1`. One file per run × scenario.

## Status vocabulary

`MEASURED` (number from an actual run), `OBSERVED` (behavior from an actual run),
`NOT TESTED`, `INCONCLUSIVE`. Unmeasured values are `null`, never `0`.

## Fields

| Field | Meaning |
|---|---|
| `run_id`, `timestamp` (UTC), `git_commit`, `git_dirty` | provenance |
| `transport` | `offline` only in Phase 1 |
| `runtime`, `runtime_version` | runtime adapter and installed SDK version (`null` if absent) |
| `stt_provider`/`stt_model`, `llm_provider`/`llm_model`, `tts_provider`/`tts_model` | exactly as configured; `null` model = not configured |
| `scenario_id` | dataset dialogue id |
| `status` | overall evidence status of this result |
| `success` | all scenario oracles held; `null` if not run |
| `hard_failures` | list of hard failure codes (see BENCHMARK_METHOD.md) |
| `latency` | `caller_voice_latency`, `pipeline_latency`, `endpointing`, `stt_final`, `llm_ttft`, `tts_ttfb`; each with `status`, `scope`, `n`, `p50_ms`, `p95_ms`, `max_ms` |
| `tools` | proposals, executed, rejected, unknown tool attempts, unauthorized attempts/executions, duplicate side effects, `correct_tool_selected` + `selection_status` |
| `booking` | expected/observed outcome and slot, calendar create calls, false success statements, `success_spoken`, `unknown_fail_closed` |
| `entities` | WER and per-field ratios, or `NOT TESTED` with reason |
| `conversation` | endpoint/interruption/context metrics, or `NOT TESTED` with reason |
| `runtime_metrics` | startup ms, CPU seconds, max RSS, session cleanup, crashed, errors |
| `errors` | exception class names only (messages may contain secrets) |
| `cost` | always `null` in Phase 1 (no usage evidence) |
| `notes` | scope statements or the exact missing prerequisites |

A `NOT TESTED` result (runtime or provider unavailable) has `latency`, `tools`, `booking`
and `runtime_metrics` set to `null` and lists every missing prerequisite in `notes`.

## STT gate result (`stt-deepgram/summary.json`)

Schema `voiceos.benchmark.stt_gate/1` (`stt_gate.SttGateResult`): provenance, `provider`,
`model`, `language`, `sdk_version`, `audio_source`, `streaming`, `status`
(`STT_BASELINE_VERIFIED` / `STT_BASELINE_FAILED` / `NOT_TESTED`), `network_hosts`,
`network_peers`, `notes` and per case: audio hash and length, `connected`,
`final_transcript` (synthetic speech of synthetic data only), `final_present`,
`empty_transcript`, interim/final counts, `connect_ms`, `first_transcript_ms`,
`last_final_ms`, `audio_sent_ms`, `close_ms`, `wall_ms`, provider `request_id`, `error`,
`match_policy`, `normalized_match`, WER counts, `entities`, `correction_final_ok`. No
API key, header or SDK object is ever written. `<case>.events.jsonl`: `kind`, `t_ms` only.

## LLM gate result (`llm-openai/summary.json`)

Schema `voiceos.benchmark.llm_gate/1` (`llm_gate.LlmGateResult`): provenance, `provider`,
`api` (`responses`), `model`, `resolved_models`, `reasoning_effort`, `sdk_version`,
`prompt_sha256`, `tool_schema_sha256`, `status` (`LLM_BASELINE_VERIFIED` /
`LLM_BASELINE_FAILED` / `NOT_TESTED`), `network_hosts`, `network_peers`, `notes`; per case
`api_ok`, `provider_error`, `first_output_ms`, `total_ms`, token counts, `tool_proposed`,
`proposed_tool`, `proposal_count`, `arguments` (synthetic), `correct_tool`,
`schema_conform`, `entity_correct`, `authority_fields`, `unknown_tool`, gateway
decision/reason/outcome, `calendar_creates_during_case`, `hard_failures`,
`quality_misses`. No API key, header or SDK object is ever written.

## TTS gate result (`tts-elevenlabs/summary.json`)

Schema `voiceos.benchmark.tts_gate/1` (`tts_gate.TtsGateResult`): provenance, `provider`,
`model_id`, `voice_id`, `voice_name`, `language`, `output_format`, `sample_rate_hz`,
`sdk_version`, `streaming`, `status` (`TTS_BASELINE_VERIFIED` / `TTS_BASELINE_FAILED` /
`NOT_TESTED`; the Cartesia challenger uses `TTS_CHALLENGER_VERIFIED` / `TTS_CHALLENGER_FAILED`),
`network_hosts`, `network_peers`, `notes`; per case `characters`,
`request_ok`, `provider_error`, `first_audio_ms`, `total_ms`, `chunk_count`,
`audio_bytes`, `audio` checks (`non_empty`, `whole_samples`, `decodable`, `duration_ms`,
`not_silent`, `alignment_complete`, `not_truncated`, `valid`), `character_cost`,
`request_id`, `audio_sha256`. No API key, header value other than the two allowlisted
ones, or SDK object is ever written.

## E2E gate result (`livekit-e2e/summary.json`, `pipecat-e2e/summary.json`)

Schema `voiceos.benchmark.e2e_gate/1` (`e2e_gate.E2EGateResult`): provenance, `runtime`,
`runtime_version`, `livekit_server_url` (loopback only), `stt` / `llm` / `tts` (provider,
model, language or reasoning, voice id, SDK version), `prompt_sha256`, `endpointing_ms`,
`input_source`, `status` (`LIVEKIT_E2E_VERIFIED` / `LIVEKIT_E2E_FAILED`, or
`PIPECAT_E2E_VERIFIED` / `PIPECAT_E2E_FAILED`),
`latency_summary` (happy path, per metric `n`, `min`, `p50`, `p95`, `max`),
`secret_scan_clean`, `network_hosts`, `network_peers`, `notes`. Per session: `name`, `room`,
`joined_identity`, `runtime_completed`, `runtime_error` (class name only), `turns` (input
text, input WAV + SHA-256, STT transcript, spoken text, model texts, tool steps, audio
duration, `reply_heard`, errors), `gateway_calls` (audit rows), `booking_outcome`,
`calendar_creates`, `bench_bookings`, `canary_bookings`, `crm_updates`,
`context_unchanged`, `startup_ms` (runtime start → caller subscribed to the agent audio),
`cleanup_ms` (caller hang-up → server lists the room without participants),
`room_empty_after_session`, `room_deleted`, `latencies` (per turn), `hard_failures`,
`checks`, `passed`.
Per-session `events.jsonl` rows: `t_ms` (relative to the session's first event), `source`
(`agent` / `caller` / `harness`), `name`, `turn`, `attrs`.

## Turn-taking gate result (`<run_id>/turn-taking/summary.json`)

Schema `voiceos.benchmark.turn_gate/1` (`turn_gate.TurnGateResult`): provenance
(`run_id`, `timestamp`, `git_commit`, `git_dirty`), `header` (LiveKit server URL –
loopback only –, runtime versions, STT/LLM/TTS provider, model, language, voice id,
`endpointing_ms`, `finalize_on_vad_end`, `prompt_sha256`, `input_source`, repetitions),
`settings` (native turn-taking settings per runtime), `input_audio_sha256` (per case and
segment), `status` (per runtime, see below), `summary` (per runtime), `runs`,
`secret_scan_clean`, `network_hosts`, `network_peers`, `notes`.

Per run (`turn_taking.TurnRunResult`, unknown keys rejected):

| Field | Meaning |
|---|---|
| `runtime`, `case_id`, `category`, `repetition`, `room` | identity of the session |
| `completed` | the runtime arm finished its session without its own error |
| `runtime_error` | the runtime arm's own error (class name only); never a provider failure |
| `harness_error` | harness/infrastructure exception (class name only, e.g. token or connection) |
| `provider_failures` | list of `{component: stt\|llm\|tts, provider, error_class, http_status, provider_code}`; safe identifiers only, never message text or credentials |
| `provider_errors` | the same failures as readable strings, e.g. `tts:cartesia:APIStatusError:402:quota_exceeded` |
| `validity` | `VALID`, `INVALID_PROVIDER_FAILURE`, `INVALID_RUNTIME_FAILURE` or `INVALID_HARNESS_FAILURE` (precedence harness > provider > runtime) |
| `valid` | derived: `validity == VALID`; only valid sessions enter any metric |
| `transcripts`, `spoken`, `tools` | committed final transcripts per turn (synthetic speech only), spoken replies, gateway tool steps |
| `hard_failures`, `tools_only_after_final`, `room_cleaned_up` | security and cleanup invariants |
| `metrics` | per-run definitions from BENCHMARK_METHOD.md (VAD/endpoint/STT-final latencies, false/late endpoint, `barge_valid`, interruption detection, TTS stop latency, missed interruption, context loss, barge-in success) |
| `entity_ok` | expected digits found in turns 0–1 (phone and self-correction cases); turns split further are not covered |

Per runtime `summary`: nearest-rank latency stats (`n`, `min`, `p50`, `p95`, `max`; turn
latencies over valid runs without false endpoint, barge-in latencies over valid runs),
`runs`, `valid_runs`, `false_endpoint`, `late_endpoint`, `barge_valid`, `barge_success`,
`missed_interruptions`, `context_loss` (each `[count, population]`), `single_turn_runs`,
`validity` (count per class), `provider_failures` (count per failure string) and
`evidence`: per group (`normal`, `endpointing`, `phone`, `barge_in`) `usable`, `runs`,
`minimum`, `sufficient`. Usable = `VALID`; for `barge_in` additionally `barge_valid`
(assistant audible when the caller started interrupting). A group is sufficient with at
least `minimum` usable runs **and** at least 90 % of its runs usable (minimums 3 / 9 / 3 / 9).

Status per runtime (`turn_taking.gate_status`, identical for both arms):
`TURN_TAKING_FAILED` on any security violation (hard failure, gateway execution without a
final transcript) or on observed interruption defects (context loss, > 10 % missed among
usable barge-in runs); `INCONCLUSIVE` if < 90 % of runs are valid or any evidence group is
insufficient (`0 missed / 0 usable` is missing evidence, never a pass);
`TURN_TAKING_VERIFIED` only if every group meets its minimum and nothing failed.

Per-session `events.jsonl` rows: `t_ms`, `source` (`agent` / `caller` / `harness`), `name`,
`turn`, `attrs` (`TTS_DONE` carries `ok` and, on failure, the safe `error` string).
`caller_frames.json`: `[t_ms, peak]` per received 20 ms frame.

## Events (`<scenario>.events.jsonl`)

One JSON object per line: `seq`, `scenario_id`, `event`, `t_ns` (monotonic, relative to
session start), `turn`, `attrs`. Only `tool`, `outcome`, `reason`, `error` attributes are
written; tool names outside the allowlist are written as `<unknown>`.

Events: `SESSION_STARTED`, `INTERRUPT_OPPORTUNITY`, `USER_AUDIO_END`, `STT_FINAL`,
`LLM_REQUESTED`, `LLM_FIRST_TOKEN`, `TOOL_PROPOSED`, `TOOL_EXECUTED`, `TOOL_REJECTED`,
`TTS_REQUESTED`, `TTS_FIRST_AUDIO`, `AI_AUDIO_START`, `AI_AUDIO_END`, `SESSION_ERROR`,
`SESSION_ENDED`.
