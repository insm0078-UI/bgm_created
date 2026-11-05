"""Split multi-version requests into batches ACE-Step can handle reliably.

ACE-Step's LM generates audio codes for all versions in one batch; with long tracks
(e.g. 600 s x 4) it can drop a sequence and fail with a tensor-size mismatch. Requests are
therefore chunked by total audio length, and any batch that still fails is retried one
version at a time.
"""

from typing import Any, Callable

from loguru import logger

from bgm_engine.errors import BatchCodesError
from bgm_engine.jobs import ProgressFn

MAX_BATCH_AUDIO_SECONDS = 360.0

# run_chunk(batch_size, report, seed_offset) -> results
ChunkFn = Callable[[int, ProgressFn, int], list[dict[str, Any]]]


def plan_batches(variations: int, duration: float,
                 max_audio_seconds: float = MAX_BATCH_AUDIO_SECONDS) -> list[int]:
    """Return batch sizes summing to ``variations`` with each batch under the audio budget."""
    per_batch = max(1, int(max_audio_seconds // max(duration, 1.0)))
    sizes = []
    remaining = variations
    while remaining > 0:
        sizes.append(min(per_batch, remaining))
        remaining -= sizes[-1]
    return sizes


def _scaled(report: ProgressFn, start: float, span: float) -> ProgressFn:
    """Map a chunk's 0..1 progress into its slice of the whole job."""
    return lambda value, desc: report(start + span * value, desc)


def run_in_batches(run_chunk: ChunkFn, variations: int, duration: float,
                   report: ProgressFn) -> list[dict[str, Any]]:
    """Run ``run_chunk`` over the planned batches, retrying failed batches singly.

    Args:
        run_chunk: Generates ``n`` versions; raises ``BatchCodesError`` on the LM batch failure.
        variations: Total number of versions requested.
        duration: Track length in seconds.
        report: Job progress callback.
    """
    sizes = plan_batches(variations, duration)
    results: list[dict[str, Any]] = []
    done = 0
    for size in sizes:
        span = size / variations
        start = done / variations
        try:
            results += run_chunk(size, _scaled(report, start, span), done)
        except BatchCodesError:
            logger.warning(f"batch of {size} failed in LM; retrying one version at a time")
            for i in range(size):
                single = _scaled(report, start + span * i / size, span / size)
                results += run_chunk(1, single, done + i)
        done += size
    return results
