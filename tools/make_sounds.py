#!/usr/bin/env python3
"""
tools/make_sounds.py
~~~~~~~~~~~~~~~~~~~~
Synthesize short placeholder WAV files for the OpenBoard sound effects.
Stdlib only: wave, math, random, struct.

Usage:
    python tools/make_sounds.py [--force]
"""

from __future__ import annotations

import argparse
import math
import os
import random
import struct
import wave
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SAMPLE_RATE: int = 44100
CHANNELS: int = 1
SAMPLE_WIDTH: int = 2          # 16-bit
PEAK_AMPLITUDE: float = 0.6    # normalise target
FADE_SAMPLES: int = 220        # ~5 ms fade in/out
RNG_SEED: int = 42

# Output directory (relative to repo root, which is tools/../)
_REPO_ROOT = Path(__file__).parent.parent
OUT_DIR: Path = _REPO_ROOT / "assets" / "build" / "sounds"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _ms_to_samples(ms: float) -> int:
    """Convert milliseconds to a sample count."""
    return int(SAMPLE_RATE * ms / 1000)


def _sine(freq: float, duration_ms: float, amplitude: float = 1.0) -> list[float]:
    """Generate a pure sine wave."""
    n = _ms_to_samples(duration_ms)
    return [amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE) for i in range(n)]


def _noise(duration_ms: float, amplitude: float = 1.0) -> list[float]:
    """Generate white noise."""
    n = _ms_to_samples(duration_ms)
    return [amplitude * random.uniform(-1.0, 1.0) for _ in range(n)]


def _decay(samples: list[float], half_life_ms: float) -> list[float]:
    """Apply an exponential decay envelope."""
    half = _ms_to_samples(half_life_ms)
    factor = math.pow(0.5, 1.0 / max(half, 1))
    env = 1.0
    result: list[float] = []
    for s in samples:
        result.append(s * env)
        env *= factor
    return result


def _mix(*tracks: list[float]) -> list[float]:
    """Mix multiple tracks (sum, same length as the longest)."""
    length = max(len(t) for t in tracks)
    out = [0.0] * length
    for track in tracks:
        for i, v in enumerate(track):
            out[i] += v
    return out


def _silence(duration_ms: float) -> list[float]:
    return [0.0] * _ms_to_samples(duration_ms)


def _fade(samples: list[float], fade_n: int | None = None) -> list[float]:
    """Apply fade-in and fade-out."""
    if fade_n is None:
        fade_n = FADE_SAMPLES
    n = len(samples)
    fade_n = min(fade_n, n // 2)
    result = list(samples)
    for i in range(fade_n):
        t = i / fade_n
        result[i] *= t
        result[n - 1 - i] *= t
    return result


def _normalise(samples: list[float], peak: float = PEAK_AMPLITUDE) -> list[float]:
    """Scale so that the absolute peak equals *peak*."""
    if not samples:
        return samples
    mx = max(abs(s) for s in samples)
    if mx < 1e-9:
        return samples
    factor = peak / mx
    return [s * factor for s in samples]


def _to_wav_bytes(samples: list[float]) -> bytes:
    """Encode float samples in [-1, 1] to 16-bit PCM bytes."""
    int_max = 32767
    packed = struct.pack(f"<{len(samples)}h", *[max(-32768, min(int_max, int(s * int_max))) for s in samples])
    return packed


def _write_wav(path: Path, samples: list[float]) -> None:
    """Write samples to a 16-bit mono WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = _to_wav_bytes(samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)


# ---------------------------------------------------------------------------
# Sound recipes
# ---------------------------------------------------------------------------


def _sound_move() -> list[float]:
    """40 ms wooden tick: noise burst + decaying 180 Hz sine."""
    noise = _decay(_noise(40.0, 0.8), half_life_ms=8.0)
    tone = _decay(_sine(180.0, 40.0, 0.5), half_life_ms=15.0)
    return _fade(_normalise(_mix(noise, tone)))


def _sound_capture() -> list[float]:
    """70 ms heavier tick."""
    noise = _decay(_noise(70.0, 1.0), half_life_ms=12.0)
    tone = _decay(_sine(130.0, 70.0, 0.6), half_life_ms=20.0)
    tone2 = _decay(_sine(260.0, 30.0, 0.3), half_life_ms=8.0)
    return _fade(_normalise(_mix(noise, tone, tone2)))


def _sound_check() -> list[float]:
    """Two quick rising tones."""
    t1 = _decay(_sine(440.0, 60.0, 0.8), half_life_ms=25.0)
    t2 = _decay(_sine(660.0, 60.0, 0.8), half_life_ms=25.0)
    gap = _silence(20.0)
    combined = t1 + gap + t2
    return _fade(_normalise(combined))


def _sound_castle() -> list[float]:
    """Two ticks 90 ms apart."""
    tick1 = _decay(_mix(_noise(40.0, 0.7), _sine(180.0, 40.0, 0.4)), half_life_ms=10.0)
    gap = _silence(90.0)
    tick2 = _decay(_mix(_noise(40.0, 0.7), _sine(180.0, 40.0, 0.4)), half_life_ms=10.0)
    combined = tick1 + gap + tick2
    return _fade(_normalise(combined))


def _sound_game_end() -> list[float]:
    """Three descending tones."""
    t1 = _decay(_sine(660.0, 100.0, 0.8), half_life_ms=40.0)
    t2 = _decay(_sine(550.0, 100.0, 0.8), half_life_ms=40.0)
    t3 = _decay(_sine(440.0, 150.0, 0.8), half_life_ms=60.0)
    gap = _silence(30.0)
    combined = t1 + gap + t2 + gap + t3
    return _fade(_normalise(combined))


def _sound_click() -> list[float]:
    """15 ms UI tick."""
    noise = _decay(_noise(15.0, 0.9), half_life_ms=4.0)
    tone = _decay(_sine(800.0, 15.0, 0.4), half_life_ms=4.0)
    return _fade(_normalise(_mix(noise, tone)), fade_n=50)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

SOUNDS: dict[str, object] = {
    "move": _sound_move,
    "capture": _sound_capture,
    "check": _sound_check,
    "castle": _sound_castle,
    "game_end": _sound_game_end,
    "click": _sound_click,
}


def main() -> None:
    """Generate all placeholder sound files."""
    parser = argparse.ArgumentParser(description="Synthesize placeholder WAV sound effects.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args()

    random.seed(RNG_SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, fn in SOUNDS.items():
        path = OUT_DIR / f"{name}.wav"
        if path.exists() and not args.force:
            print(f"  skip  {path.name}  (use --force to overwrite)")
            continue
        samples = fn()  # type: ignore[operator]
        _write_wav(path, samples)
        size_kb = path.stat().st_size / 1024
        print(f"  wrote {path.name}  {size_kb:.1f} KB  ({len(samples)} samples)")


if __name__ == "__main__":
    main()
