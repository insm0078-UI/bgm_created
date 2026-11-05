"""HTTP routes for history, edited previews, and WAV/MP3 export."""

import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from bgm_engine.editing import EditError, Edits, render, write_audio
from bgm_engine.history import HistoryStore


class EditsBody(BaseModel):
    """Edit settings sent by the UI."""

    trim_start: float = Field(default=0, ge=0)
    trim_end: float | None = Field(default=None, gt=0)
    fade_in: float = Field(default=0, ge=0, le=30)
    fade_out: float = Field(default=0, ge=0, le=30)
    gain_db: float = Field(default=0, ge=-12, le=12)


class PreviewBody(BaseModel):
    """Request to render an edited preview of a track."""

    id: str
    edits: EditsBody = Field(default_factory=EditsBody)


class ExportBody(PreviewBody):
    """Request to export a (possibly edited) track to a user-chosen file."""

    format: Literal["wav", "mp3"] = "wav"
    dest: str = Field(min_length=1)


def build_edit_router(history: HistoryStore, output_dir: str, auth) -> APIRouter:
    """Create routes bound to the history store and output folder.

    Args:
        history: Store used to resolve track ids to files (clients never pass source paths).
        output_dir: Folder where preview renders are written.
        auth: FastAPI dependency enforcing the engine token.
    """
    router = APIRouter(dependencies=[Depends(auth)])
    preview_dir = os.path.join(output_dir, "previews")

    def source_path(track_id: str) -> str:
        track = history.get(track_id)
        if track is None or not track["exists"]:
            raise HTTPException(status_code=404, detail="원본 음악 파일을 찾을 수 없습니다.")
        return track["path"]

    def rendered(body: PreviewBody):
        try:
            return render(source_path(body.id), Edits(**body.edits.model_dump()))
        except EditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/history")
    def list_history(limit: int = 300) -> list[dict[str, Any]]:
        return history.list(limit=min(max(limit, 1), 1000))

    @router.delete("/history/{track_id}")
    def delete_track(track_id: str) -> dict[str, Any]:
        track = history.delete(track_id)
        if track is None:
            raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
        # Only files the engine created (inside output_dir) are removed; user exports are untouched.
        removed = [p for p in (track["path"], os.path.join(preview_dir, f"{track_id}.wav"))
                   if _remove_inside(output_dir, p)]
        return {"id": track_id, "removed_files": len(removed)}

    @router.post("/preview")
    def preview(body: PreviewBody) -> dict[str, Any]:
        data, sr = rendered(body)
        dest = os.path.join(preview_dir, f"{body.id}.wav")
        try:
            write_audio(data, sr, dest, "wav")
        except EditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"path": dest, "duration": len(data) / sr}

    @router.post("/export")
    def export(body: ExportBody) -> dict[str, Any]:
        data, sr = rendered(body)
        try:
            write_audio(data, sr, body.dest, body.format)
        except EditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"파일을 저장하지 못했습니다: {exc}") from exc
        return {"path": body.dest, "duration": len(data) / sr}

    return router


def _remove_inside(root: str, path: str) -> bool:
    """Delete ``path`` if it is an existing file inside ``root``; return True if removed."""
    real_root = os.path.realpath(root)
    real = os.path.realpath(path)
    try:
        inside = os.path.commonpath([real_root, real]) == real_root
    except ValueError:  # different drives
        return False
    if not inside or not os.path.isfile(real):
        return False
    os.remove(real)
    return True
