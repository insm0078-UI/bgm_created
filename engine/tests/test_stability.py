"""Regression tests for the stability review fixes."""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from fastapi.testclient import TestClient

from bgm_engine import jobs
from bgm_engine.editing import Edits, apply_edits
from bgm_engine.errors import OOM_MESSAGE, friendly_error, is_oom
from bgm_engine.jobs import GenerateRequest, JobStore
from bgm_engine.runtime import EngineRuntime
from bgm_engine.server import create_app


class FriendlyErrorTest(unittest.TestCase):
    """ACE-Step returns OOM as text; it must become a Korean message."""

    def test_cuda_and_preflight_oom_are_recognised(self):
        for raw in ("CUDA out of memory. Tried to allocate 2.00 GiB",
                    "Error: Insufficient free VRAM: need ~9.1 GB, only 2.0 GB available."):
            self.assertTrue(is_oom(raw))
            self.assertEqual(friendly_error(raw), OOM_MESSAGE)

    def test_other_errors_keep_detail_without_prefix(self):
        self.assertEqual(friendly_error("Error: bad input"), "음악을 만들지 못했습니다: bad input")
        self.assertIn("다시 시도", friendly_error(None))

    def test_runtime_maps_failed_result_to_friendly_oom(self):
        rt = EngineRuntime("root", tempfile.gettempdir())
        rt.state = "ready"
        failed = MagicMock(success=False, error="CUDA out of memory", status_message="")
        with patch("acestep.inference.generate_music", return_value=failed), \
                patch("bgm_engine.runtime._release_gpu_cache") as release:
            with self.assertRaises(RuntimeError) as ctx:
                rt._run_acestep({"task_type": "text2music"}, 1, "c", 10, lambda v, d: None)
        self.assertEqual(str(ctx.exception), OOM_MESSAGE)
        release.assert_called_once()


class JobPruneTest(unittest.TestCase):
    """Finished jobs are capped so a long session does not grow memory forever."""

    def test_old_finished_jobs_are_dropped(self):
        with patch.object(jobs, "MAX_FINISHED_JOBS", 3):
            store = JobStore(lambda req, report: [])
            ids = [store.submit(GenerateRequest()).id for _ in range(6)]
            deadline = time.time() + 3
            while time.time() < deadline and store.get(ids[0]) is not None:
                time.sleep(0.01)  # pruning runs after each job finishes
            self.assertIsNone(store.get(ids[0]))
            self.assertEqual(store.get(ids[-1]).status, "done")


class TrimToleranceTest(unittest.TestCase):
    """A rounded-up end (e.g. 34.6 for a 34.59 s clip) means "until the end"."""

    def test_end_slightly_past_duration_is_clamped(self):
        data = np.zeros((3459, 2), dtype=np.float32)  # 34.59 s at 100 Hz
        out = apply_edits(data, 100, Edits(trim_start=1, trim_end=34.6))
        self.assertEqual(len(out), 3359)

    def test_end_far_past_duration_still_rejected(self):
        from bgm_engine.editing import EditError
        with self.assertRaises(EditError):
            apply_edits(np.zeros((3459, 2), dtype=np.float32), 100, Edits(trim_end=35.0))


class AudioRouteHardeningTest(unittest.TestCase):
    """/audio serves WAV files only, never the history database."""

    def test_non_wav_files_are_not_served(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "history.db")
            wav = os.path.join(tmp, "a.wav")
            for path in (db, wav):
                with open(path, "wb") as f:
                    f.write(b"x")
            runtime = MagicMock(state="ready", message="", output_dir=tmp)
            client = TestClient(create_app(runtime, JobStore(lambda r, p: []), "t"))
            self.assertEqual(client.get("/audio", params={"path": db, "t": "t"}).status_code, 404)
            self.assertEqual(client.get("/audio", params={"path": wav, "t": "t"}).status_code, 200)



class BatchingTest(unittest.TestCase):
    """Long multi-version requests are split; LM batch failures retry one by one."""

    def test_plan_batches(self):
        from bgm_engine.batching import plan_batches
        self.assertEqual(plan_batches(4, 60), [4])
        self.assertEqual(plan_batches(4, 180), [2, 2])
        self.assertEqual(plan_batches(4, 600), [1, 1, 1, 1])
        self.assertEqual(plan_batches(1, 600), [1])
        self.assertEqual(sum(plan_batches(3, 150)), 3)

    def test_batch_failure_falls_back_to_singles(self):
        from bgm_engine.batching import run_in_batches
        from bgm_engine.errors import BatchCodesError
        calls, progress = [], []

        def chunk(size, report, offset):
            calls.append((size, offset))
            report(1.0, "x")
            if size > 1:
                raise BatchCodesError("Error in batch codes generation: size mismatch")
            return [{"id": f"t{offset}"}]

        results = run_in_batches(chunk, 3, 60, lambda v, d: progress.append(v))
        self.assertEqual([r["id"] for r in results], ["t0", "t1", "t2"])
        self.assertEqual(calls, [(3, 0), (1, 0), (1, 1), (1, 2)])
        self.assertLessEqual(max(progress), 1.0 + 1e-9)

    def test_other_errors_are_not_retried(self):
        from bgm_engine.batching import run_in_batches

        def chunk(size, report, offset):
            raise RuntimeError("GPU 메모리가 부족합니다.")

        with self.assertRaises(RuntimeError):
            run_in_batches(chunk, 2, 60, lambda v, d: None)

    def test_runtime_raises_batch_error_only_for_multi_batch(self):
        from bgm_engine.errors import BatchCodesError
        rt = EngineRuntime("root", tempfile.gettempdir())
        rt.state = "ready"
        failed = MagicMock(success=False, error="Error in batch codes generation: (3) vs (4)",
                           status_message="")
        with patch("acestep.inference.generate_music", return_value=failed):
            with self.assertRaises(BatchCodesError):
                rt._run_acestep({"task_type": "text2music"}, 4, "c", 600, lambda v, d: None)
            with self.assertRaises(RuntimeError) as ctx:
                rt._run_acestep({"task_type": "text2music"}, 1, "c", 600, lambda v, d: None)
        self.assertNotIsInstance(ctx.exception, BatchCodesError)



class GpuLimitsTest(unittest.TestCase):
    """Requests above the GPU tier limits are rejected before reaching the model."""

    def _client(self, limits):
        runtime = MagicMock(state="ready", message="", output_dir=tempfile.gettempdir(),
                            limits=limits)
        runtime.gpu_info.return_value = None
        return TestClient(create_app(runtime, JobStore(lambda r, p: []), "t"))

    def test_health_reports_limits(self):
        body = self._client({"max_duration": 480, "max_variations": 4}).get(
            "/health", headers={"X-Engine-Token": "t"}).json()
        self.assertEqual(body["limits"], {"max_duration": 480, "max_variations": 4})

    def test_over_limit_requests_rejected_in_korean(self):
        client = self._client({"max_duration": 480, "max_variations": 2})
        h = {"X-Engine-Token": "t"}
        long = client.post("/generate", headers=h, json={"duration": 600})
        self.assertEqual(long.status_code, 400)
        self.assertIn("480초", long.json()["detail"])
        many = client.post("/generate", headers=h, json={"duration": 60, "variations": 4})
        self.assertEqual(many.status_code, 400)
        self.assertEqual(client.post("/generate", headers=h, json={"duration": 480}).status_code,
                         200)

    def test_gpu_limits_reads_acestep_tier(self):
        from bgm_engine.limits import gpu_limits
        cfg = MagicMock(max_duration_with_lm=480, max_batch_size_with_lm=8)
        with patch("acestep.gpu_config.get_global_gpu_config", return_value=cfg):
            self.assertEqual(gpu_limits(), {"max_duration": 480, "max_variations": 4})


if __name__ == "__main__":
    unittest.main()
