"""ACE-Step model lifecycle and the generation calls used by the job worker."""

import os
import threading
import time
from typing import Any

import soundfile as sf
from loguru import logger

from bgm_engine.acestep_params import result_entry, text2music_kwargs, variation_kwargs
from bgm_engine.audio_fx import dialogue_eq
from bgm_engine.jobs import GenerateRequest, ProgressFn
from bgm_engine.korean_keywords import mood_hint
from bgm_engine.limits import DEFAULT_LIMITS, gpu_limits
from bgm_engine.prompt_builder import (
    MOOD_TAGS,
    build_lm_query,
    build_tag_caption,
    ensure_instruments,
    sanitize_caption,
)
from bgm_engine.batching import run_in_batches
from bgm_engine.errors import (
    OOM_MESSAGE,
    BatchCodesError,
    friendly_error,
    is_batch_codes_error,
    is_oom,
)
from bgm_engine.scene import extra_tags, recommend

DIT_MODEL = "acestep-v15-turbo"
LM_MODEL = "acestep-5Hz-lm-1.7B"


class EngineRuntime:
    """Owns the ACE-Step DiT/LM handlers and exposes load state and generation."""

    def __init__(self, project_root: str, output_dir: str):
        """Prepare paths; models are loaded later by ``load_async``."""
        self.project_root = project_root
        self.output_dir = output_dir
        self.state = "loading"  # loading | ready | error
        self.message = "AI 모델을 불러오는 중"
        self._dit = None
        self._llm = None
        self._gpu_lock = threading.Lock()
        self.limits = dict(DEFAULT_LIMITS)

    def load_async(self) -> None:
        """Start loading models on a background thread."""
        threading.Thread(target=self._load, name="model-loader", daemon=True).start()

    def _load(self) -> None:
        try:
            from acestep.handler import AceStepHandler
            from acestep.llm_inference import LLMHandler

            t0 = time.time()
            dit = AceStepHandler()
            msg, ok = dit.initialize_service(
                project_root=self.project_root, config_path=DIT_MODEL, device="auto")
            if not ok:
                raise RuntimeError(msg)
            llm = LLMHandler()
            msg, ok = llm.initialize(
                checkpoint_dir=os.path.join(self.project_root, "checkpoints"),
                lm_model_path=LM_MODEL, backend="vllm", device="auto")
            if not ok:
                raise RuntimeError(msg)
            self._dit, self._llm = dit, llm
            self.limits = gpu_limits()
            self.state, self.message = "ready", "AI 준비 완료"
            logger.info(f"models ready in {time.time() - t0:.1f}s")
        except Exception as exc:  # noqa: BLE001 - reported to UI via /health
            logger.exception("model load failed")
            self.state, self.message = "error", f"AI 모델을 불러오지 못했습니다: {exc}"

    def gpu_info(self) -> dict[str, Any] | None:
        """Return GPU name and memory usage in GB, or None without CUDA."""
        import torch

        if not torch.cuda.is_available():
            return None
        free, total = torch.cuda.mem_get_info()
        return {"name": torch.cuda.get_device_name(0), "total_gb": round(total / 1024**3, 1),
                "used_gb": round((total - free) / 1024**3, 1)}

    def _locked(self, fn, *args):
        """Run ``fn`` holding the GPU lock, mapping CUDA OOM to a friendly error."""
        if self.state != "ready":
            raise RuntimeError("AI 모델이 아직 준비되지 않았습니다.")
        import torch

        with self._gpu_lock:
            try:
                return fn(*args)
            except torch.cuda.OutOfMemoryError as exc:
                torch.cuda.empty_cache()
                raise RuntimeError(OOM_MESSAGE) from exc

    def _create_sample_caption(self, query: str) -> tuple[str, int | None, str] | None:
        from acestep.inference import create_sample

        sample = create_sample(self._llm, query=query, instrumental=True)
        if not sample.success or not sample.caption:
            logger.warning(f"create_sample failed: {sample.error}")
            return None
        return sample.caption, sample.bpm, sample.keyscale

    def analyze(self, scene: str) -> dict[str, Any]:
        """Recommend mood/instruments for a Korean scene description via the LM."""
        def run():
            out = self._create_sample_caption(build_lm_query(scene, None, "", []))
            if out is None:
                raise RuntimeError("장면을 분석하지 못했습니다. 다시 시도해 주세요.")
            caption = sanitize_caption(out[0])
            return {**recommend(caption, scene), "caption": caption, "bpm": out[1]}
        return self._locked(run)

    def generate(self, request: GenerateRequest, report: ProgressFn) -> list[dict[str, Any]]:
        """Generate instrumental tracks for a text-to-music request."""
        return self._locked(self._generate_locked, request, report)

    def vary(self, track: dict[str, Any], similarity: float,
             report: ProgressFn) -> list[dict[str, Any]]:
        """Generate a new version that keeps the feel of ``track``."""
        def run():
            report(0.05, "비슷한 버전을 만드는 중")
            return self._run_acestep(variation_kwargs(track, similarity), 1, track["caption"],
                                     track["duration"], report)
        return self._locked(run)

    def _resolve_caption(self, request: GenerateRequest, report: ProgressFn):
        """Return (caption, bpm, keyscale) from presets or the LM-converted description."""
        # Description and scene preset are combined: the preset's tags are added to the caption.
        extra = extra_tags(request.preset, request.dialogue_mode)
        has_text = request.description.strip() or (not request.mood and request.custom_mood.strip())
        if has_text:
            report(0.05, "설명을 분석하는 중")
            # The LM may drift from Korean scenes; pin the chosen/detected mood in the caption.
            mood = mood_hint(request.mood, request.custom_mood, request.description)
            out = self._create_sample_caption(build_lm_query(
                request.description, mood, request.custom_mood, request.instruments))
            if out is not None:
                caption = ensure_instruments(out[0], request.instruments)
                pinned = ", ".join(t for t in (MOOD_TAGS.get(mood or ""), extra) if t)
                return sanitize_caption(caption, pinned), out[1], out[2]
        return build_tag_caption(request.mood, request.instruments, extra), None, ""

    def _generate_locked(self, request: GenerateRequest, report: ProgressFn):
        caption, bpm, keyscale = self._resolve_caption(request, report)
        fixed = request.seed >= 0

        def chunk(size: int, chunk_report: ProgressFn, offset: int):
            seed = request.seed + offset if fixed else -1
            kwargs = text2music_kwargs(caption, request.duration, bpm, keyscale, seed)
            return self._run_acestep(kwargs, size, caption, request.duration, chunk_report,
                                     fixed_seed=fixed)

        results = run_in_batches(chunk, request.variations, request.duration, report)
        if request.dialogue_mode:
            for r in results:
                data, sr = sf.read(r["path"], dtype="float32", always_2d=True)
                sf.write(r["path"], dialogue_eq(data, sr), sr, subtype="PCM_16")
        return results

    def _run_acestep(self, kwargs: dict[str, Any], batch: int, caption: str, duration: float,
                     report: ProgressFn, fixed_seed: bool = False) -> list[dict[str, Any]]:
        from acestep.inference import GenerationConfig, GenerationParams, generate_music

        config = GenerationConfig(batch_size=batch, audio_format="wav",
                                  use_random_seed=not fixed_seed)
        save_dir = os.path.join(self.output_dir, time.strftime("%Y%m%d"))
        os.makedirs(save_dir, exist_ok=True)
        result = generate_music(
            self._dit, self._llm, GenerationParams(**kwargs), config, save_dir=save_dir,
            progress=lambda value, desc=None, **_: report(0.1 + 0.9 * float(value), "음악을 만드는 중"))
        report(0.99, "마무리하는 중")  # raises JobCancelled if the user cancelled meanwhile
        if not result.success:
            raw = result.error or result.status_message or ""
            if is_oom(raw):
                _release_gpu_cache()
            if batch > 1 and is_batch_codes_error(raw):
                raise BatchCodesError(raw)
            raise RuntimeError(friendly_error(raw))
        lm_meta = (result.extra_outputs or {}).get("lm_metadata") or {}
        return [result_entry(a, caption, duration, lm_meta, kwargs, DIT_MODEL, LM_MODEL)
                for a in result.audios]



def _release_gpu_cache() -> None:
    """Free cached CUDA blocks after an out-of-memory failure so the next attempt can fit."""
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
