"""Tests for scene recommendation, presets, loops, dialogue EQ, cancel, and variations."""

import os
import sqlite3
import tempfile
import threading
import time
import unittest

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from bgm_engine.audio_fx import LoopError, dialogue_eq, loop_points, make_loop
from bgm_engine.history import HistoryStore
from bgm_engine.jobs import GenerateRequest, JobStore, VariationRequest
from bgm_engine.pipeline import build_runner
from bgm_engine.prompt_builder import INSTRUMENTAL_SUFFIX, build_tag_caption
from bgm_engine.scene import PRESETS, extra_tags, recommend
from bgm_engine.server import create_app

TOKEN = "t"
H = {"X-Engine-Token": TOKEN}


def wait_status(store, job_id, statuses=("done", "failed", "cancelled"), timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = store.get(job_id)
        if job.status in statuses:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job stuck in {store.get(job_id).status}")


class RecommendAndPresetTest(unittest.TestCase):
    """Caption keywords map to UI mood/instrument keys; presets add tags."""

    def test_recommend_from_lm_caption(self):
        caption = ("A gentle, bittersweet and lonely acoustic guitar piece with soft piano, "
                   "nostalgic and melancholic")
        rec = recommend(caption)
        self.assertEqual(rec["mood"], "sad")
        self.assertEqual(rec["instruments"][:2], ["acoustic_guitar", "piano"])

    def test_korean_scene_words_override_misleading_caption(self):
        lm_caption = "A clean acoustic guitar with a pensive, slightly melancholic feel"
        rec = recommend(lm_caption, "어두운 복도에서 누군가 뒤따라오는 발소리가 들리는 장면")
        self.assertEqual(rec["mood"], "tension")
        self.assertEqual(recommend("calm piece", "친구들이 장난치며 웃는 쉬는 시간")["mood"], "comedy")

    def test_korean_instrument_words(self):
        self.assertIn("music_box", recommend("soft", "오르골 소리처럼 잔잔한")["instruments"])

    def test_korean_mood_helper(self):
        from bgm_engine.korean_keywords import korean_mood
        self.assertEqual(korean_mood("이별 후 혼자 우는 장면"), "sad")
        self.assertIsNone(korean_mood("그냥 음악"))

    def test_description_and_preset_are_combined(self):
        tags = extra_tags("comedy", True)
        self.assertIn(PRESETS["comedy"], tags)
        self.assertIn("soft underscore for dialogue", tags)

    def test_mood_hint_priority(self):
        from bgm_engine.korean_keywords import mood_hint
        scene = "이별 후 어두운 방에 혼자 있는 장면"
        self.assertEqual(mood_hint("comedy", "", scene), "comedy")
        self.assertIsNone(mood_hint(None, "비 오는 카페처럼 차분한", scene))
        self.assertEqual(mood_hint(None, "  ", scene), "sad")
        self.assertIsNone(mood_hint(None, "", "그냥 음악"))

    def test_custom_mood_reaches_lm_query_despite_scene_words(self):
        from bgm_engine.korean_keywords import mood_hint
        from bgm_engine.prompt_builder import build_lm_query
        custom, scene = "비 오는 카페처럼 차분한", "이별 후 어두운 방"
        query = build_lm_query(scene, mood_hint(None, custom, scene), custom, [])
        self.assertIn(f"Mood: {custom}", query)

    def test_recommend_with_no_keywords(self):
        self.assertEqual(recommend("something"), {"mood": None, "instruments": []})

    def test_presets_add_tags_without_choosing_mood_or_instruments(self):
        for key in PRESETS:
            caption = build_tag_caption(None, [], extra_tags(key, False))
            self.assertIn(PRESETS[key], caption)
            self.assertNotIn("featuring", caption, key)
            self.assertTrue(caption.endswith(INSTRUMENTAL_SUFFIX), key)

    def test_preset_tags_name_no_instruments(self):
        from bgm_engine.prompt_builder import INSTRUMENT_TAGS
        for key, tags in PRESETS.items():
            for name in INSTRUMENT_TAGS.values():
                self.assertNotIn(name.split()[-1], tags, (key, name))

    def test_dialogue_tags_included_once_suffix(self):
        caption = build_tag_caption("daily", [], extra_tags("daily_talk", True))
        self.assertIn("soft underscore for dialogue", caption)
        self.assertEqual(caption.count("no vocals"), 1)

    def test_unknown_preset_rejected(self):
        with self.assertRaises(ValueError):
            extra_tags("nope", False)


class LoopTest(unittest.TestCase):
    """Loops cut on bar boundaries and join seamlessly."""

    SR = 1000

    def test_bar_aligned_length(self):
        self.assertEqual(loop_points(30.0, 120), (24.0, 2.0))

    def test_seam_is_continuous(self):
        data = np.random.default_rng(0).standard_normal((30 * self.SR, 2)).astype(np.float32) * 0.1
        out, length = make_loop(data, self.SR, 120)
        n = int(length * self.SR)
        self.assertEqual(len(out), n)
        np.testing.assert_allclose(out[-1], data[n - 1], atol=1e-6)
        np.testing.assert_allclose(out[0], data[n], atol=1e-6)

    def test_repeat_to_target_with_end_fade(self):
        data = np.full((30 * self.SR, 2), 0.5, dtype=np.float32)
        out, _ = make_loop(data, self.SR, 120, repeat_to=100)
        self.assertEqual(len(out), 100 * self.SR)
        self.assertAlmostEqual(float(out[-1, 0]), 0.0, places=4)

    def test_too_short_raises(self):
        with self.assertRaises(LoopError):
            make_loop(np.zeros((5 * self.SR, 2)), self.SR, 60)


class DialogueEqTest(unittest.TestCase):
    """Speech band is reduced more than the low band."""

    def test_presence_band_dipped(self):
        sr = 48000
        t = np.arange(sr) / sr
        def level(freq):
            sig = np.stack([np.sin(2 * np.pi * freq * t)] * 2, axis=1).astype(np.float32) * 0.5
            return float(np.abs(dialogue_eq(sig, sr)[sr // 2:]).max())
        self.assertLess(level(2500), level(200) * 0.75)


class CancelTest(unittest.TestCase):
    """Cancel stops running jobs at the next progress report and skips queued ones."""

    def test_cancel_running_and_queued(self):
        started = threading.Event()

        def run(req, report):
            started.set()
            for _ in range(200):
                report(0.5, "working")
                time.sleep(0.01)
            return [{"id": "never"}]

        store = JobStore(run)
        running = store.submit(GenerateRequest())
        queued = store.submit(GenerateRequest())
        started.wait(2)
        store.cancel(queued.id)
        store.cancel(running.id)
        self.assertEqual(wait_status(store, running.id).status, "cancelled")
        self.assertEqual(store.get(queued.id).status, "cancelled")
        self.assertEqual(store.get(running.id).results, [])


class FakeRuntime:
    """GPU-free runtime used by pipeline/route tests."""

    def __init__(self, output_dir, path):
        self.state, self.message, self.output_dir, self.path = "ready", "ok", output_dir, path

    def gpu_info(self):
        return None

    def analyze(self, scene):
        return {"mood": "sad", "instruments": ["piano"], "caption": "c", "bpm": 70}

    def _entry(self, track_id):
        return {"id": track_id, "path": self.path, "created_at": "2026-11-05 14:00:00",
                "duration": 30, "caption": "c", "seed": 1, "bpm": 120, "keyscale": "C major",
                "dit_model": "turbo", "lm_model": "lm"}

    def generate(self, request, report):
        return [self._entry("gen1")]

    def vary(self, track, similarity, report):
        report(0.5, "vary")
        return [self._entry("var1")]


class PipelineAndRoutesTest(unittest.TestCase):
    """Variations/loops become new history tracks linked to their parent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src.wav")
        sf.write(self.src, np.zeros((30 * 48000, 2), dtype=np.float32), 48000)
        self.history = HistoryStore(os.path.join(self.tmp.name, "h.db"))
        self.runtime = FakeRuntime(self.tmp.name, self.src)
        self.store = JobStore(build_runner(self.runtime, self.history))
        self.client = TestClient(create_app(self.runtime, self.store, TOKEN, self.history))
        job = self.client.post("/generate", headers=H, json={"preset": "sad"}).json()
        wait_status(self.store, job["id"])

    def tearDown(self):
        self.history._conn.close()
        self.tmp.cleanup()

    def test_generate_records_preset_request(self):
        track = self.history.get("gen1")
        self.assertEqual(track["kind"], "generated")
        self.assertEqual(track["request"]["preset"], "sad")

    def test_variation_job_records_parent(self):
        job = self.client.post("/variation", headers=H, json={"id": "gen1"}).json()
        self.assertEqual(wait_status(self.store, job["id"]).status, "done")
        var = self.history.get("var1")
        self.assertEqual((var["kind"], var["parent_id"]), ("variation", "gen1"))

    def test_variation_unknown_track_404(self):
        self.assertEqual(self.client.post("/variation", headers=H, json={"id": "x"}).status_code, 404)

    def test_loop_route_creates_loop_track(self):
        resp = self.client.post("/loop", headers=H, json={"id": "gen1", "repeat_to": 60})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["loop_seconds"], 24.0)
        self.assertAlmostEqual(sf.info(body["path"]).duration, 60.0, places=2)
        self.assertEqual(self.history.get(body["id"])["kind"], "loop")

    def test_analyze_and_cancel_routes(self):
        self.assertEqual(self.client.post("/analyze", headers=H, json={"scene": "공원 벤치"})
                         .json()["mood"], "sad")
        self.assertEqual(self.client.post("/jobs/none/cancel", headers=H).status_code, 404)
        self.runtime.state = "loading"
        self.assertEqual(self.client.post("/analyze", headers=H, json={"scene": "공원"})
                         .status_code, 503)

    def test_generate_rejects_unknown_preset(self):
        self.assertEqual(self.client.post("/generate", headers=H, json={"preset": "x"})
                         .status_code, 422)


class MigrationTest(unittest.TestCase):
    """Databases from phase 3 gain the new columns without losing rows."""

    def test_old_schema_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "h.db")
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE tracks (id TEXT PRIMARY KEY, path TEXT NOT NULL, "
                         "created_at TEXT NOT NULL, duration REAL, caption TEXT, seed INTEGER, "
                         "bpm INTEGER, keyscale TEXT, dit_model TEXT, lm_model TEXT, "
                         "request_json TEXT NOT NULL)")
            conn.execute("INSERT INTO tracks VALUES ('old', 'p', '2026-11-05', 30, 'c', 1, 90, "
                         "'C', 'd', 'l', '{}')")
            conn.commit()
            conn.close()
            store = HistoryStore(db)
            old = store.get("old")
            store._conn.close()
            self.assertEqual((old["kind"], old["parent_id"]), ("generated", None))


if __name__ == "__main__":
    unittest.main()
