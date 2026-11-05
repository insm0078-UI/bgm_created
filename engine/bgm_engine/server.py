"""FastAPI app exposing health, generation jobs, and audio files to the desktop UI."""

import os
import secrets
from typing import Any, Protocol

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from bgm_engine.edit_routes import build_edit_router
from bgm_engine.history import HistoryStore
from bgm_engine.jobs import GenerateRequest, JobStore
from bgm_engine.limits import DEFAULT_LIMITS, limit_error
from bgm_engine.prompt_builder import INSTRUMENT_TAGS, MOOD_TAGS
from bgm_engine.scene import PRESETS
from bgm_engine.scene_routes import build_scene_router

ALLOWED_ORIGINS = ["http://tauri.localhost", "https://tauri.localhost", "http://localhost:1420"]


class Runtime(Protocol):
    """Subset of EngineRuntime the server depends on (eases testing)."""

    state: str
    message: str
    output_dir: str

    def gpu_info(self) -> dict[str, Any] | None: ...


class GenerateBody(BaseModel):
    """HTTP body for POST /generate."""

    mood: str | None = None
    custom_mood: str = Field(default="", max_length=200)
    instruments: list[str] = Field(default_factory=list)
    duration: float = Field(default=60, ge=10, le=600)
    description: str = Field(default="", max_length=1000)
    variations: int = Field(default=1, ge=1, le=4)
    seed: int = -1
    preset: str | None = None
    dialogue_mode: bool = False

    @field_validator("preset")
    @classmethod
    def _check_preset(cls, value: str | None) -> str | None:
        if value is not None and value not in PRESETS:
            raise ValueError(f"unknown preset: {value}")
        return value

    @field_validator("mood")
    @classmethod
    def _check_mood(cls, value: str | None) -> str | None:
        if value is not None and value not in MOOD_TAGS:
            raise ValueError(f"unknown mood: {value}")
        return value

    @field_validator("instruments")
    @classmethod
    def _check_instruments(cls, value: list[str]) -> list[str]:
        unknown = [v for v in value if v not in INSTRUMENT_TAGS]
        if unknown:
            raise ValueError(f"unknown instruments: {unknown}")
        return list(dict.fromkeys(value))


def create_app(runtime: Runtime, store: JobStore, token: str,
               history: HistoryStore | None = None) -> FastAPI:
    """Build the FastAPI application.

    Args:
        runtime: Model runtime providing state, GPU info and output folder.
        store: Job store that executes generation requests.
        token: Shared secret required on every request.
        history: Track history; enables /history, /preview and /export when given.

    Returns:
        Configured FastAPI app.
    """
    app = FastAPI(title="AI BGM Studio Engine")
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["X-Engine-Token"])

    def require_token(x_engine_token: str | None = Header(default=None),
                      t: str | None = Query(default=None)) -> None:
        supplied = x_engine_token or t or ""
        if not secrets.compare_digest(supplied, token):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health", dependencies=[Depends(require_token)])
    def health() -> dict[str, Any]:
        return {"state": runtime.state, "message": runtime.message, "gpu": runtime.gpu_info(),
                "limits": getattr(runtime, "limits", DEFAULT_LIMITS)}

    @app.post("/generate", dependencies=[Depends(require_token)])
    def generate(body: GenerateBody) -> dict[str, Any]:
        if runtime.state != "ready":
            raise HTTPException(status_code=503, detail="AI 모델이 아직 준비되지 않았습니다.")
        too_big = limit_error(getattr(runtime, "limits", DEFAULT_LIMITS), body.duration,
                              body.variations)
        if too_big:
            raise HTTPException(status_code=400, detail=too_big)
        job = store.submit(GenerateRequest(**body.model_dump()))
        return job.to_dict()

    @app.get("/jobs/{job_id}", dependencies=[Depends(require_token)])
    def get_job(job_id: str) -> dict[str, Any]:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.to_dict()

    @app.post("/jobs/{job_id}/cancel", dependencies=[Depends(require_token)])
    def cancel_job(job_id: str) -> dict[str, Any]:
        job = store.cancel(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.to_dict()

    @app.get("/audio", dependencies=[Depends(require_token)])
    def audio(path: str) -> FileResponse:
        # Only engine-written WAV files are served (never history.db or other files).
        if (not path.lower().endswith(".wav") or not _is_inside(runtime.output_dir, path)
                or not os.path.isfile(path)):
            raise HTTPException(status_code=404, detail="audio not found")
        return FileResponse(os.path.realpath(path), media_type="audio/wav",
                            headers={"Cache-Control": "no-store"})

    if history is not None:
        app.include_router(build_edit_router(history, runtime.output_dir, require_token))
        app.include_router(build_scene_router(runtime, store, history, require_token))
    return app


def _is_inside(root: str, path: str) -> bool:
    """Return True if ``path`` resolves inside ``root`` (False across drives)."""
    real_root = os.path.realpath(root)
    try:
        return os.path.commonpath([real_root, os.path.realpath(path)]) == real_root
    except ValueError:
        return False
