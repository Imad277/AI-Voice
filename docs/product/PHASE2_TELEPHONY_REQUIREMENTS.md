# Phase 2 – Telephony Requirements

**Status: PROPOSED / NOT DECIDED.** No carrier, SIP provider or telephony architecture is
selected (D-06). Real PSTN calls require explicit authorization by the owner (project
rule 23); outbound campaigns require consent/suppression first (rule 25 and section 4).

## 1. Requirements

| Area | Requirement | Phase |
|---|---|---|
| Inbound | German geographic numbers routed to an agent deployment; answer within a defined ring budget; caller ID passed as untrusted data | 2B |
| Number model | E.164, globally unique in the platform; capabilities (voice, SMS); status lifecycle (`reserved`, `active`, `porting`, `released`) | 2B |
| Provisioning | buy/assign numbers via carrier API with regulatory data (address/identity bundles where required) | 2B |
| Forwarding | customer forwards an existing number to a platform number (fastest onboarding path) | 2B |
| Porting | port existing numbers in; asynchronous process with status tracking | 2C |
| Caller ID (outbound) | only verified numbers owned by the tenant; no spoofing | 2C |
| DTMF | receive DTMF (RFC 4733 / SIP INFO) as input events; never as authority | 2B |
| Transfers | warm/cold transfer to human numbers configured in routing rules; allowlisted destinations | 2B |
| Human handoff | transfer with whisper/summary to the agent's escalation target; callback task when unavailable | 2B (transfer), 2C (summary) |
| Voicemail / no answer | out-of-hours or failure path: take a message, create callback task | 2B |
| Recording | off by default; tenant policy + consent prompt; dual-channel optional; stored encrypted with retention | 2B (policy), opt-in |
| Outbound | API-triggered single calls, later campaigns; consent and suppression gate before dialing; time-of-day and frequency limits | 2C |
| SIP / BYOC | customers connect their own SIP trunk/PBX | 2C |
| Codecs | G.711 A-law (Germany) on PSTN legs; Opus on WebRTC; transcoding in the media layer; STT quality on 8 kHz must be measured before 2B launch | 2B |
| Emergency | the AI agent must never be the path for emergency calls; numbers used for AI agents must not be presented as emergency-capable lines; on emergency intent: instruct to dial 112/110 and offer transfer only where legally permitted | 2B (design + legal review) |
| Fraud prevention | outbound destination allowlist (no premium-rate, no international by default), per-tenant spend caps, rate limits, anomaly alerts, KYC before outbound | 2B (inbound caps), 2C (outbound) |
| Reliability | carrier failover or graceful busy/voicemail; concurrent call limits per tenant; drain on deploy | 2B |
| Observability | SIP response codes, call setup time, media quality (jitter, packet loss), per-carrier error rates | 2B |

## 2. Architectural options (not ranked)

| Option | Shape | Strengths | Concerns |
|---|---|---|---|
| **T0: carrier SIP trunk → SIP ingress of the media layer → rooms** | carrier delivers SIP to a SIP gateway (e.g. LiveKit SIP) that bridges into the same media rooms used for browser test calls | one media path for WebRTC and PSTN; matches Phase 1 runtime setup; carrier exchangeable | SIP/SBC operations, NAT/TLS/SRTP, needs media-layer decision (D-14) |
| **T1: CPaaS media streams** | CPaaS (e.g. Twilio, Telnyx) answers the call and streams audio over WebSocket to the voice runtime | fast start, numbers + regulatory bundles via API | second media path besides WebRTC; per-stream limits; data path and EU residency per provider to verify |
| **German SIP trunk providers** | e.g. sipgate, easybell, Telekom business trunks into our SIP ingress | German numbers, local support | research found reselling/commercial-use restrictions and limited APIs for provisioning – contract review required |
| **BYOC** | customer PBX/trunk connects to our SIP ingress | enterprise fit | 2C; interoperability testing per PBX |

Research input (not decisions): `docs/research/manus/audit/05_Telephony_Infrastructure_Audit.md`
compares Twilio, Telnyx, sipgate, easybell, Placetel and Telekom.

**No carrier and no telephony shape is selected.** The architecture stays carrier-neutral
through the telephony adapter contract below; the voice runtime never depends on a carrier.
Evaluation hypothesis (not a default): terminating carrier calls in the media layer (T0
shape) would let browser test calls and phone calls share one data plane. Before D-06,
evaluate one CPaaS/carrier with German number provisioning API and one German trunk
provider against the requirements above in a single, decision-scoped spike (number
provisioning, inbound to runtime, transfer, DTMF, G.711 STT quality, EU data path,
contract terms for reselling).

### Telephony adapter contract (stable interface)

| Operation / event | Shape |
|---|---|
| `incoming_call` | verified dialed number (routing key), caller number (untrusted), carrier call ref, media attachment info → session manager |
| `answer`, `hangup`, `reject` | by carrier call ref |
| `transfer` | to an allowlisted destination; result event (`completed`, `failed`, `no_answer`) |
| `dtmf` | digits as untrusted input events |
| `call_ended` / CDR | duration per leg, end cause, carrier cost reference → usage events |
| `provision_number`, `release_number`, `port_number` | asynchronous operations through the operation ledger |
| Webhook/event authenticity | provider signature verification inside the adapter; unsigned events rejected |

Carrier SIP trunks, CPaaS media streams and BYOC are implementations of this contract plus a
media session implementation.

## 3. Evidence needed before D-06

1. Inbound call from a German number reaches an agent in the target media path, with
   measured setup time and caller-perceived latency (no synthetic loopback).
2. STT entity accuracy on 8 kHz G.711 audio (phone numbers, dates, names) against the
   Phase 1 synthetic set re-rendered at 8 kHz, then a small consented human set.
3. Transfer to an external number and DTMF reception.
4. Number provisioning and regulatory flow for German numbers via API; porting process.
5. Contract review: reselling to business customers, AI/voicebot usage, data processing
   location, recording, emergency-call obligations.
6. Cost model per minute, per number, per channel.

## 4. Outbound prerequisites (2C)

Consent capture and evidence per contact, suppression list checked server-side before
every dial, calling-time windows, frequency caps, caller-ID verification, campaign
pause/stop, audit of every dial decision, legal review of B2B/B2C cold-calling rules. No
outbound campaign execution before these exist and are approved.
