"""Turn raw ACE-Step/CUDA error strings into short Korean messages for the UI."""

OOM_MESSAGE = "GPU 메모리가 부족합니다. 음악 길이나 버전 수를 줄여서 다시 시도해 주세요."
_OOM_MARKERS = ("out of memory", "insufficient free vram", "cuda error: out of memory")


class BatchCodesError(RuntimeError):
    """ACE-Step's LM dropped sequences while generating several versions at once."""


def is_batch_codes_error(message: str) -> bool:
    """Return True for ACE-Step's batched LM code-generation failure (retryable one by one)."""
    return "batch codes generation" in message.lower()


def is_oom(message: str) -> bool:
    """Return True if an error message describes GPU memory exhaustion."""
    lowered = message.lower()
    return any(marker in lowered for marker in _OOM_MARKERS)


def friendly_error(message: str | None) -> str:
    """Map an engine error to a user-facing Korean message.

    ACE-Step catches its own exceptions (including CUDA OOM) and returns them as strings,
    so OOM must be recognised from text rather than by exception type.
    """
    text = (message or "").strip()
    if is_oom(text):
        return OOM_MESSAGE
    if not text:
        return "음악을 만들지 못했습니다. 다시 시도해 주세요."
    return f"음악을 만들지 못했습니다: {text.removeprefix('Error: ')}"
