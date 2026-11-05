"""Job dispatcher: runs each request type on the runtime and records results in history."""

from typing import Any, Callable

from bgm_engine.history import HistoryStore
from bgm_engine.jobs import GenerateRequest, ProgressFn, VariationRequest


def build_runner(runtime, history: HistoryStore) -> Callable[[Any, ProgressFn], list[dict]]:
    """Return the JobStore run function bound to ``runtime`` and ``history``.

    Args:
        runtime: Object with ``generate(request, report)`` and ``vary(track, sim, report)``.
        history: Store that records every finished track.
    """
    def run(request: Any, report: ProgressFn) -> list[dict[str, Any]]:
        if isinstance(request, GenerateRequest):
            results = runtime.generate(request, report)
            history.add_many(request, results)
            return results
        if isinstance(request, VariationRequest):
            track = history.get(request.track_id)
            if track is None or not track["exists"]:
                raise RuntimeError("원본 음악 파일을 찾을 수 없습니다.")
            results = runtime.vary(track, request.similarity, report)
            history.add_many(track["request"], results, kind="variation", parent_id=track["id"])
            return results
        raise TypeError(f"unsupported request: {type(request).__name__}")

    return run
