"""Tests for the job store and HTTP server using a fake runtime (no GPU)."""

import os
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from bgm_engine.jobs import GenerateRequest, JobStore
from bgm_engine.server import create_app

TOKEN = "test-token"
HEADERS = {"X-Engine-Token": TOKEN}


def wait_for(store, job_id, timeout=2.0):
    """Poll until the job leaves queued/running."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = store.get(job_id)
        if job.status in ("done", "failed"):
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


class FakeRuntime:
    """Runtime stand-in with configurable state."""

    def __init__(self, output_dir, state="ready"):
        self.state = state
        self.message = state
        self.output_dir = output_dir

    def gpu_info(self):
        return {"name": "Fake GPU", "total_gb": 16.0, "used_gb": 1.0}


class JobStoreTest(unittest.TestCase):
    """JobStore runs jobs and records success or failure."""

    def test_success_records_results_and_progress(self):
        def run(req, report):
            report(0.5, "half")
            return [{"id": "a", "duration": req.duration}]

        store = JobStore(run)
        job = wait_for(store, store.submit(GenerateRequest(duration=30)).id)
        self.assertEqual(job.status, "done")
        self.assertEqual(job.progress, 1.0)
        self.assertEqual(job.results, [{"id": "a", "duration": 30}])

    def test_failure_keeps_error_message(self):
        def run(req, report):
            raise RuntimeError("GPU 메모리가 부족합니다.")

        store = JobStore(run)
        job = wait_for(store, store.submit(GenerateRequest()).id)
        self.assertEqual(job.status, "failed")
        self.assertIn("GPU 메모리", job.error)


class ServerTest(unittest.TestCase):
    """HTTP contract: auth, validation, readiness, and audio path safety."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = FakeRuntime(self.tmp.name)
        self.store = JobStore(lambda req, report: [{"id": "x", "mood": req.mood}])
        self.client = TestClient(create_app(self.runtime, self.store, TOKEN))

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_missing_token(self):
        self.assertEqual(self.client.get("/health").status_code, 401)

    def test_health_reports_state_and_gpu(self):
        body = self.client.get("/health", headers=HEADERS).json()
        self.assertEqual(body["state"], "ready")
        self.assertEqual(body["gpu"]["name"], "Fake GPU")

    def test_generate_then_poll_job(self):
        resp = self.client.post("/generate", headers=HEADERS,
                                json={"mood": "romance", "instruments": ["piano"]})
        self.assertEqual(resp.status_code, 200)
        wait_for(self.store, resp.json()["id"])
        job = self.client.get(f"/jobs/{resp.json()['id']}", headers=HEADERS).json()
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["results"][0]["mood"], "romance")

    def test_generate_validates_inputs(self):
        for body in ({"mood": "nope"}, {"instruments": ["kazoo"]}, {"duration": 5},
                     {"variations": 9}):
            resp = self.client.post("/generate", headers=HEADERS, json=body)
            self.assertEqual(resp.status_code, 422, body)

    def test_generate_rejected_while_loading(self):
        self.runtime.state = "loading"
        resp = self.client.post("/generate", headers=HEADERS, json={})
        self.assertEqual(resp.status_code, 503)

    def test_audio_served_only_inside_output_dir(self):
        inside = os.path.join(self.tmp.name, "a.wav")
        with open(inside, "wb") as f:
            f.write(b"RIFF")
        ok = self.client.get("/audio", params={"path": inside, "t": TOKEN})
        self.assertEqual(ok.status_code, 200)
        outside = self.client.get("/audio", params={"path": __file__, "t": TOKEN})
        self.assertEqual(outside.status_code, 404)


if __name__ == "__main__":
    unittest.main()
