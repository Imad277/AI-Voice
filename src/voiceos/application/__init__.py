"""Application layer (Phase 2): use cases and orchestration of the modular monolith.

Uses the domain, the runtime contracts and the Phase 0 core (Tool Gateway, booking,
tenancy). Never imports infrastructure adapters directly (they implement ports and are
wired in at the composition root), never provider/runtime SDKs, test mocks or
``voiceos.benchmark``. Split by plane:

- ``control_plane``: configuration and administration (organizations, users, agents, agent
  versions, deployments, integrations, configuration, usage views).
- ``data_plane``: realtime call execution (call sessions, media, STT, LLM, TTS, turn
  handling, tool proposals through the gateway, runtime events).

The planes are internal module boundaries of one deployable, not separate services.
"""
