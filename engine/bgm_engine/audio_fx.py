"""Audio processing: seamless BGM loops and a dialogue-friendly EQ."""

import math

import numpy as np
from scipy.signal import lfilter

LOOP_MIN_SECONDS = 4.0
END_FADE_SECONDS = 3.0
DIALOGUE_EQ_HZ = 2500.0
DIALOGUE_EQ_DB = -4.0
DIALOGUE_EQ_Q = 0.9
DIALOGUE_GAIN_DB = -3.0


class LoopError(ValueError):
    """Raised when a track is too short to build a loop."""


def _bar_seconds(bpm: float | None) -> float | None:
    return 240.0 / bpm if bpm and 30 <= bpm <= 300 else None


def loop_points(duration: float, bpm: float | None) -> tuple[float, float]:
    """Choose (loop_length, crossfade) in seconds aligned to 4/4 bars when BPM is known.

    Raises:
        LoopError: If the track cannot hold a loop of at least ``LOOP_MIN_SECONDS``.
    """
    bar = _bar_seconds(bpm)
    xfade = min(max(bar if bar else 2.0, 0.5), 3.0)
    available = duration - xfade
    if bar:
        bars = math.floor(available / bar + 1e-6)
        if bars >= 8:
            bars -= bars % 4  # prefer whole 4-bar phrases
        length = bars * bar
    else:
        length = available
    if length < LOOP_MIN_SECONDS:
        raise LoopError("곡이 너무 짧아서 반복 음악을 만들 수 없습니다.")
    return length, xfade


def make_loop(data: np.ndarray, sr: int, bpm: float | None,
              repeat_to: float | None = None) -> tuple[np.ndarray, float]:
    """Build a seamlessly repeating clip, optionally tiled to ``repeat_to`` seconds.

    The tail just after the loop end is crossfaded into the loop start, so playing the
    clip back-to-back has no audible seam.

    Args:
        data: Samples (frames x channels).
        sr: Sample rate.
        bpm: Track tempo used to cut on bar boundaries (None = no alignment).
        repeat_to: If given, repeat the loop to this length and fade out the end.

    Returns:
        (audio, loop_length_seconds)
    """
    length, xfade = loop_points(len(data) / sr, bpm)
    n, x = int(round(length * sr)), int(round(xfade * sr))
    out = data[:n].astype(np.float32, copy=True)
    t = np.linspace(0.0, 1.0, x, dtype=np.float32).reshape(-1, 1)
    out[:x] = data[:x] * np.sin(t * np.pi / 2) + data[n:n + x] * np.cos(t * np.pi / 2)
    if repeat_to:
        total = int(round(repeat_to * sr))
        out = np.tile(out, (math.ceil(total / n), 1))[:total]
        fade = min(int(END_FADE_SECONDS * sr), total)
        out[total - fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32).reshape(-1, 1)
    return np.clip(out, -1.0, 1.0), length


def _peaking_coeffs(sr: int, freq: float, gain_db: float, q: float):
    """RBJ audio-EQ-cookbook peaking filter coefficients (b, a)."""
    a_gain = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * freq / sr
    alpha = math.sin(w0) / (2 * q)
    b = np.array([1 + alpha * a_gain, -2 * math.cos(w0), 1 - alpha * a_gain])
    a = np.array([1 + alpha / a_gain, -2 * math.cos(w0), 1 - alpha / a_gain])
    return b / a[0], a / a[0]


def dialogue_eq(data: np.ndarray, sr: int) -> np.ndarray:
    """Dip the speech-presence band and lower level so dialogue sits on top of the music."""
    b, a = _peaking_coeffs(sr, DIALOGUE_EQ_HZ, DIALOGUE_EQ_DB, DIALOGUE_EQ_Q)
    out = lfilter(b, a, data, axis=0).astype(np.float32)
    out *= 10 ** (DIALOGUE_GAIN_DB / 20)
    return np.clip(out, -1.0, 1.0)
