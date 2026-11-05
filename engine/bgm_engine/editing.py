"""Non-destructive audio edits (trim, fades, gain) and WAV/MP3 writing."""

import os
from dataclasses import dataclass

import numpy as np
import soundfile as sf

FORMATS = {"wav": ("WAV", "PCM_16"), "mp3": ("MP3", "MPEG_LAYER_III")}
MP3_BEST_QUALITY = 0.0  # libsndfile compression_level 0.0 ~= 320 kbps CBR
MAX_GAIN_DB = 12.0
END_TOLERANCE_S = 0.1


class EditError(ValueError):
    """Raised when edit parameters do not fit the audio."""


@dataclass
class Edits:
    """Edit settings in seconds / decibels; defaults mean "unchanged"."""

    trim_start: float = 0.0
    trim_end: float | None = None
    fade_in: float = 0.0
    fade_out: float = 0.0
    gain_db: float = 0.0

    def is_identity(self) -> bool:
        """Return True if applying these edits would not change the audio."""
        return (self.trim_start == 0 and self.trim_end is None and self.fade_in == 0
                and self.fade_out == 0 and self.gain_db == 0)


def _fade_curve(n: int) -> np.ndarray:
    """Smooth 0->1 raised-cosine ramp of length n."""
    return 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, n))


def apply_edits(data: np.ndarray, sr: int, edits: Edits) -> np.ndarray:
    """Return an edited copy of ``data`` (frames x channels).

    Args:
        data: Audio samples, shape (frames,) or (frames, channels).
        sr: Sample rate in Hz.
        edits: Edit settings.

    Returns:
        New array; the input is not modified.

    Raises:
        EditError: If the trim range is empty/out of bounds or values are negative.
    """
    duration = len(data) / sr
    end = duration if edits.trim_end is None else edits.trim_end
    if duration < end <= duration + END_TOLERANCE_S:
        end = duration  # UI shows lengths rounded to 0.1 s; treat that as "until the end"
    if edits.trim_start < 0 or end > duration or end - edits.trim_start < 1.0:
        raise EditError("자르기 구간이 올바르지 않습니다. (최소 1초 이상 남겨야 합니다)")
    if edits.fade_in < 0 or edits.fade_out < 0:
        raise EditError("'서서히 시작/끝내기' 시간은 0초 이상이어야 합니다.")
    if abs(edits.gain_db) > MAX_GAIN_DB:
        raise EditError(f"볼륨은 ±{MAX_GAIN_DB:.0f}dB 범위에서 조절할 수 있습니다.")

    out = data[int(round(edits.trim_start * sr)):int(round(end * sr))].astype(np.float32, copy=True)
    frames = len(out)
    shape = (-1, 1) if out.ndim == 2 else (-1,)
    fade_in = min(int(edits.fade_in * sr), frames)
    fade_out = min(int(edits.fade_out * sr), frames)
    if fade_in > 0:
        out[:fade_in] *= _fade_curve(fade_in).reshape(shape)
    if fade_out > 0:
        out[frames - fade_out:] *= _fade_curve(fade_out)[::-1].reshape(shape)
    if edits.gain_db:
        out *= 10 ** (edits.gain_db / 20)
    return np.clip(out, -1.0, 1.0)


def render(src_path: str, edits: Edits) -> tuple[np.ndarray, int]:
    """Read ``src_path`` and return (edited_samples, sample_rate)."""
    data, sr = sf.read(src_path, dtype="float32", always_2d=True)
    return apply_edits(data, sr, edits), sr


def write_audio(data: np.ndarray, sr: int, dest: str, fmt: str) -> None:
    """Write samples to ``dest`` as WAV (16-bit) or MP3 (~320 kbps).

    Raises:
        EditError: If the format is unsupported or the extension does not match.
    """
    if fmt not in FORMATS:
        raise EditError(f"지원하지 않는 형식입니다: {fmt}")
    if not dest.lower().endswith(f".{fmt}"):
        raise EditError(f"파일 확장자가 .{fmt} 이어야 합니다.")
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    container, subtype = FORMATS[fmt]
    extra = ({"bitrate_mode": "CONSTANT", "compression_level": MP3_BEST_QUALITY}
             if fmt == "mp3" else {})
    try:
        sf.write(dest, data, sr, format=container, subtype=subtype, **extra)
    except sf.LibsndfileError as exc:
        raise EditError(f"{fmt.upper()} 파일로 저장하지 못했습니다: {exc}") from exc
