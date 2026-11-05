"""Per-GPU generation limits taken from ACE-Step's own GPU tier configuration."""

from typing import Any

UI_MAX_VARIATIONS = 4
DEFAULT_LIMITS: dict[str, int] = {"max_duration": 600, "max_variations": UI_MAX_VARIATIONS}


def gpu_limits() -> dict[str, int]:
    """Return ``{"max_duration", "max_variations"}`` for this GPU with the LM loaded.

    ACE-Step sizes these per VRAM tier (e.g. 480 s on 16 GB cards); exceeding them fails
    with an out-of-memory error, so the UI and request validation use the same numbers.
    """
    from acestep.gpu_config import get_global_gpu_config

    cfg = get_global_gpu_config()
    return {
        "max_duration": int(cfg.max_duration_with_lm),
        "max_variations": max(1, min(UI_MAX_VARIATIONS, int(cfg.max_batch_size_with_lm))),
    }


def limit_error(limits: dict[str, Any], duration: float, variations: int) -> str | None:
    """Return a Korean message if a request exceeds ``limits``, else None."""
    if duration > limits["max_duration"]:
        return f"이 그래픽카드에서는 최대 {limits['max_duration']}초까지 만들 수 있습니다."
    if variations > limits["max_variations"]:
        return f"이 그래픽카드에서는 한 번에 최대 {limits['max_variations']}개까지 만들 수 있습니다."
    return None
