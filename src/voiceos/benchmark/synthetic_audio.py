"""Local, deterministic German test speech for the STT gate (macOS only).

Uses the operating system's built-in speech synthesizer (``say``) and ``afconvert``; no
network, no cloud TTS, no microphone, no real person. Output: 16 kHz mono PCM16 WAV.
Synthetic speech is cleaner than real callers, so results are a functional baseline only.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess  # fixed local tools only (say, afconvert)
import tempfile
import wave
from pathlib import Path

VOICE = "Anna"  # macOS de_DE voice
SAY, AFCONVERT = "/usr/bin/say", "/usr/bin/afconvert"  # absolute: no PATH lookup
SAMPLE_RATE_HZ = 16_000
TIMEOUT_S = 60.0  # a hung speech synthesizer fails the run instead of stalling it


class SyntheticAudioUnavailable(Exception):
    pass


def source_description() -> str:
    return f"macOS {platform.mac_ver()[0] or 'unknown'} say voice {VOICE} (de_DE)"


def ensure_available() -> None:
    if platform.system() != "Darwin" or not (Path(SAY).exists() and Path(AFCONVERT).exists()):
        raise SyntheticAudioUnavailable("local synthesis needs macOS say and afconvert")
    voices = subprocess.run(
        ["say", "-v", "?"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if not any(line.startswith(VOICE + " ") and "de_DE" in line for line in voices.splitlines()):
        raise SyntheticAudioUnavailable(f"voice {VOICE} (de_DE) not installed")


def render(text: str, out_wav: Path) -> str:
    """Render ``text`` to ``out_wav``; returns the SHA-256 of the WAV file."""
    ensure_available()
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "speech.aiff"
        subprocess.run([SAY, "-v", VOICE, "-o", str(aiff), text], check=True, timeout=TIMEOUT_S)  # noqa: S603
        convert = [AFCONVERT, "-f", "WAVE", "-d", f"LEI16@{SAMPLE_RATE_HZ}", "-c", "1"]
        subprocess.run([*convert, str(aiff), str(out_wav)], check=True, timeout=TIMEOUT_S)  # noqa: S603
    return hashlib.sha256(out_wav.read_bytes()).hexdigest()


def read_pcm(wav_path: Path) -> bytes:
    with wave.open(str(wav_path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, SAMPLE_RATE_HZ):
            raise ValueError("expected 16 kHz mono PCM16")
        return wav.readframes(wav.getnframes())
