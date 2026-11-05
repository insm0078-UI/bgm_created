"""In-memory job queue that runs one generation at a time on a worker thread."""

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger

ProgressFn = Callable[[float, str], None]
RunFn = Callable[[Any, ProgressFn], list[dict[str, Any]]]
FINISHED = ("done", "failed", "cancelled")
MAX_FINISHED_JOBS = 100  # older finished jobs are dropped so memory stays bounded


class JobCancelled(Exception):
    """Raised from the progress callback once the user asked to cancel."""


@dataclass
class GenerateRequest:
    """Validated text-to-music request coming from the UI."""

    mood: str | None = None
    custom_mood: str = ""
    instruments: list[str] = field(default_factory=list)
    duration: float = 60.0
    description: str = ""
    variations: int = 1
    seed: int = -1
    preset: str | None = None
    dialogue_mode: bool = False


@dataclass
class VariationRequest:
    """Request for a new version that keeps the feel of an existing track."""

    track_id: str
    similarity: float = 0.5


@dataclass
class Job:
    """State of one generation job as reported to the UI."""

    id: str
    request: Any
    status: str = "queued"  # queued | running | done | failed | cancelled
    progress: float = 0.0
    message: str = "대기 중"
    results: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    cancel_requested: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the job for the HTTP API."""
        return {
            "id": self.id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "message": self.message,
            "results": self.results,
            "error": self.error,
        }


class JobStore:
    """Thread-safe job registry with a single background worker."""

    def __init__(self, run_fn: RunFn):
        """Create the store.

        Args:
            run_fn: Callable ``(request, report) -> results``; ``report`` raises
                ``JobCancelled`` after a cancel request.
        """
        self._run_fn = run_fn
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._worker = threading.Thread(target=self._work, name="bgm-worker", daemon=True)
        self._worker.start()

    def submit(self, request: Any) -> Job:
        """Queue a request and return its job."""
        job = Job(id=uuid.uuid4().hex, request=request)
        with self._lock:
            self._jobs[job.id] = job
        self._queue.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        """Return a job by id, or None."""
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        """Ask a queued/running job to stop; returns the job or None if unknown."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None and job.status in ("queued", "running"):
                job.cancel_requested = True
                job.message = "취소하는 중"
                if job.status == "queued":
                    job.status = "cancelled"
                    job.message = "취소됨"
            return job

    def _update(self, job: Job, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(job, key, value)

    def _prune(self) -> None:
        """Forget the oldest finished jobs beyond ``MAX_FINISHED_JOBS``."""
        with self._lock:
            finished = sorted((j for j in self._jobs.values() if j.status in FINISHED),
                              key=lambda j: j.created_at)
            for job in finished[:max(0, len(finished) - MAX_FINISHED_JOBS)]:
                del self._jobs[job.id]

    def _work(self) -> None:
        while True:
            job = self.get(self._queue.get())
            if job is not None and job.status == "queued":
                self._run_job(job)
            self._prune()

    def _run_job(self, job: Job) -> None:
        self._update(job, status="running", message="생성 준비 중", progress=0.01)

        def report(value: float, desc: str) -> None:
            if job.cancel_requested:
                raise JobCancelled()
            self._update(job, progress=max(job.progress, min(value, 0.99)), message=desc)

        try:
            report(0.01, "생성 준비 중")
            results = self._run_fn(job.request, report)
            self._update(job, status="done", progress=1.0, message="완료", results=results)
        except Exception as exc:  # noqa: BLE001 - surface any engine failure to the UI
            if job.cancel_requested:
                logger.info(f"job {job.id} cancelled")
                self._update(job, status="cancelled", message="취소됨")
                return
            logger.exception(f"job {job.id} failed")
            self._update(job, status="failed", message="생성 실패", error=str(exc))
