# Voice Architecture

**Status:** **NOT DECIDED.** Phase 0 contains no voice runtime and no provider integration.

## Phase 0 (implemented)

Deterministic fakes in `voiceos/mocks/voice.py` exist only so the security boundary can be
tested offline:

- `FakeSTT` – maps audio bytes to scripted transcripts.
- `FakeLLM` – returns scripted text and untrusted `ToolRequest` proposals.
- `FakeTTS` – encodes text to bytes.
- `FakeRuntime` – one loop: transcribe, apply caller affirmation to a pending readback,
  ask the LLM, send any proposal through the Tool Gateway, render speech through the guard.

The fakes define no adapter interface for real providers. They are not a runtime design.

## Fixed constraints for any future voice architecture

- The runtime holds the trusted `CallContext`; the model only proposes tool calls.
- Native speech-to-speech output must not be able to state business results that bypass
  the gateway and the speech guard.
- Providers are integrated behind explicit adapter boundaries.
- n8n never controls realtime voice execution.

## NOT DECIDED (requires validation evidence and an accepted ADR)

| Decision | Research candidates (not selected) |
|---|---|
| Voice runtime (ADR-001) | LiveKit Agents; Pipecat with LiveKit transport |
| Voice architecture (ADR-002) | cascade; native speech-to-speech; hybrid |
| STT (ADR-003) | named in research only |
| TTS (ADR-004) | named in research only |
| LLM strategy (ADR-005) | named in research only |
| Telephony (ADR-006) | named in research only |

Real calls, SIP/PSTN, recording and provider API access remain prohibited until explicitly
authorized (G0 freeze per `docs/research/manus/validation/`).
