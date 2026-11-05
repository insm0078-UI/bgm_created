"""HTTP routes for scene analysis, similar-version jobs, and seamless loops."""

import os
import time
import uuid
from typing import Any

import soundfile as sf
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from bgm_engine.audio_fx import LoopError, make_loop
from bgm_engine.history import HistoryStore
from bgm_engine.jobs import JobStore, VariationRequest


class AnalyzeBody(BaseModel):
    """Scene description to analyze."""

    scene: str = Field(min_length=2, max_length=1000)


class VariationBody(BaseModel):
    """Track to base a new version on."""

    id: str
    similarity: float = Field(default=0.5, ge=0.2, le=0.9)


class LoopBody(BaseModel):
    """Track to turn into a loop, optionally repeated to a target length."""

    id: str
    repeat_to: float | None = Field(default=None, ge=10, le=1800)


def build_scene_router(runtime, store: JobStore, history: HistoryStore, auth) -> APIRouter:
    """Create routes for analysis, variations and loops.

    Args:
        runtime: Engine runtime exposing ``state``, ``output_dir`` and ``analyze(scene)``.
        store: Job queue for GPU work.
        history: Track history used to resolve ids and record new tracks.
        auth: Dependency enforcing the engine token.
    """
    router = APIRouter(dependencies=[Depends(auth)])

    def require_ready() -> None:
        if runtime.state != "ready":
            raise HTTPException(status_code=503, detail="AI 모델이 아직 준비되지 않았습니다.")

    def existing_track(track_id: str) -> dict[str, Any]:
        track = history.get(track_id)
        if track is None or not track["exists"]:
            raise HTTPException(status_code=404, detail="원본 음악 파일을 찾을 수 없습니다.")
        return track

    @router.post("/analyze")
    def analyze(body: AnalyzeBody) -> dict[str, Any]:
        require_ready()
        try:
            return runtime.analyze(body.scene)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post("/variation")
    def variation(body: VariationBody) -> dict[str, Any]:
        require_ready()
        existing_track(body.id)
        return store.submit(VariationRequest(body.id, body.similarity)).to_dict()

    @router.post("/loop")
    def loop(body: LoopBody) -> dict[str, Any]:
        track = existing_track(body.id)
        data, sr = sf.read(track["path"], dtype="float32", always_2d=True)
        try:
            audio, loop_seconds = make_loop(data, sr, track.get("bpm"), body.repeat_to)
        except LoopError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        save_dir = os.path.join(runtime.output_dir, time.strftime("%Y%m%d"))
        os.makedirs(save_dir, exist_ok=True)
        copied = ("caption", "seed", "bpm", "keyscale", "dit_model", "lm_model")
        entry = {k: track[k] for k in copied}
        entry.update(id=uuid.uuid4().hex, duration=round(len(audio) / sr, 2),
                     created_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        entry["path"] = os.path.join(save_dir, f"{entry['id']}.wav")
        sf.write(entry["path"], audio, sr, subtype="PCM_16")
        history.add_many(track["request"], [entry], kind="loop", parent_id=track["id"])
        return {**entry, "loop_seconds": round(loop_seconds, 2)}

    return router
