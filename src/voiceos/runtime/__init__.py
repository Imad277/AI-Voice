"""Data plane contracts (Phase 2): runtime, media session, provider ports, gateway binding.

Typed contracts only, so product code never depends on a specific voice runtime, media
server or speech provider. LiveKit Agents, Pipecat, any media server and any STT/LLM/TTS
provider are later implementations in ``voiceos.infrastructure``; none is selected here
(decision register D-01, D-03..D-05, D-14). This package imports no SDK and no
``voiceos.benchmark`` module.
"""
