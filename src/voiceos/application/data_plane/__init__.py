"""Data plane use cases: call session lifecycle, media, STT/LLM/TTS orchestration, turn
handling, tool proposals through the Tool Gateway and runtime events. Reads only published,
immutable configuration; never imports the control plane and never takes tenant authority
from the model, the caller or the client."""
