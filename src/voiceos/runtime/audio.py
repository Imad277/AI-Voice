"""Audio frame shared by the media session and the speech provider ports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AudioFrame:
    """Raw 16-bit little-endian PCM."""

    pcm: bytes = field(repr=False)
    sample_rate_hz: int
    channels: int = 1
