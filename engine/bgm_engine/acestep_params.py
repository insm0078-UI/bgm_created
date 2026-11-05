"""Build ACE-Step GenerationParams for text-to-music and similar-version (cover) jobs."""

import time
from typing import Any

INFERENCE_STEPS = 8  # turbo model default


def text2music_kwargs(caption: str, duration: float, bpm: int | None, keyscale: str,
                      seed: int) -> dict[str, Any]:
    """Keyword arguments for an instrumental text-to-music generation."""
    return {
        "task_type": "text2music",
        "caption": caption,
        "lyrics": "[Instrumental]",
        "instrumental": True,
        "duration": duration,
        "bpm": bpm,
        "keyscale": keyscale or "",
        "thinking": True,
        "inference_steps": INFERENCE_STEPS,
        "seed": seed,
    }


def variation_kwargs(track: dict[str, Any], similarity: float) -> dict[str, Any]:
    """Keyword arguments for a cover-based new version of an existing track.

    Args:
        track: History record with ``path``, ``caption``, ``duration``, ``bpm``, ``keyscale``.
        similarity: 0..1; higher keeps more of the source structure.
    """
    return {
        "task_type": "cover",
        "src_audio": track["path"],
        "caption": track["caption"],
        "lyrics": "[Instrumental]",
        "instrumental": True,
        "duration": track["duration"],
        "bpm": track.get("bpm"),
        "keyscale": track.get("keyscale") or "",
        "audio_cover_strength": similarity,
        "cover_noise_strength": 0.0,
        "inference_steps": INFERENCE_STEPS,
        "seed": -1,
    }


def result_entry(audio: dict, caption: str, duration: float, lm_meta: dict,
                 kwargs: dict[str, Any], dit_model: str, lm_model: str) -> dict[str, Any]:
    """Build the per-track metadata record returned to the UI."""
    params = audio.get("params") or {}
    return {
        "id": audio.get("key"),
        "path": audio.get("path"),
        "duration": duration,
        "caption": caption,
        "seed": params.get("seed"),
        "bpm": lm_meta.get("bpm") or params.get("bpm") or kwargs.get("bpm"),
        "keyscale": lm_meta.get("keyscale") or params.get("keyscale") or kwargs.get("keyscale"),
        "dit_model": dit_model,
        "lm_model": lm_model,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
