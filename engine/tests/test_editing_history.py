"""Tests for audio edits, history persistence, and the preview/export routes."""

import os
import tempfile
import unittest

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from bgm_engine.editing import EditError, Edits, apply_edits, write_audio
from bgm_engine.history import HistoryStore
from bgm_engine.jobs import GenerateRequest, JobStore
from bgm_engine.server import create_app

SR = 1000
TOKEN = "t"
HEADERS = {"X-Engine-Token": TOKEN}


def tone(seconds=10.0, amp=0.5):
    """Constant stereo signal so fades/gain are easy to assert."""
    return np.full((int(seconds * SR), 2), amp, dtype=np.float32)


class ApplyEditsTest(unittest.TestCase):
    """apply_edits trims, fades and scales without touching the input."""

    def test_identity_returns_equal_copy(self):
        src = tone()
        out = apply_edits(src, SR, Edits())
        np.testing.assert_allclose(out, src)
        self.assertIsNot(out, src)

    def test_trim_and_fades(self):
        out = apply_edits(tone(), SR, Edits(trim_start=2, trim_end=8, fade_in=1, fade_out=2))
        self.assertEqual(len(out), 6 * SR)
        self.assertAlmostEqual(float(out[0, 0]), 0.0, places=4)
        self.assertAlmostEqual(float(out[-1, 1]), 0.0, places=4)
        self.assertAlmostEqual(float(out[3 * SR, 0]), 0.5, places=4)

    def test_gain_and_clipping(self):
        out = apply_edits(tone(amp=0.5), SR, Edits(gain_db=12))
        self.assertLessEqual(float(out.max()), 1.0)
        quiet = apply_edits(tone(amp=0.5), SR, Edits(gain_db=-6))
        self.assertAlmostEqual(float(quiet[0, 0]), 0.5 * 10 ** (-6 / 20), places=4)

    def test_rejects_bad_ranges(self):
        for edits in (Edits(trim_start=5, trim_end=5.5), Edits(trim_end=11), Edits(fade_in=-1),
                      Edits(gain_db=20)):
            with self.assertRaises(EditError, msg=edits):
                apply_edits(tone(), SR, edits)

    def test_long_fade_is_clamped_to_length(self):
        out = apply_edits(tone(2), SR, Edits(fade_in=30))
        self.assertEqual(len(out), 2 * SR)


class WriteAudioTest(unittest.TestCase):
    """write_audio produces readable WAV/MP3 and checks extensions."""

    def test_wav_and_mp3_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = np.zeros((48000, 2), dtype=np.float32)
            for fmt in ("wav", "mp3"):
                path = os.path.join(tmp, f"x.{fmt}")
                write_audio(data, 48000, path, fmt)
                self.assertAlmostEqual(sf.info(path).duration, 1.0, delta=0.1)

    def test_extension_mismatch_rejected(self):
        with self.assertRaises(EditError):
            write_audio(np.zeros((10, 2)), SR, "x.wav", "mp3")

    def test_encoder_failure_becomes_edit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(EditError):
                write_audio(np.zeros((SR, 2)), SR, os.path.join(tmp, "x.mp3"), "mp3")


class HistoryAndRoutesTest(unittest.TestCase):
    """History persists across reopen; routes resolve ids, never raw source paths."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src.wav")
        sf.write(self.src, tone(), SR)
        self.db = os.path.join(self.tmp.name, "history.db")
        self.history = HistoryStore(self.db)
        self.history.add_many(GenerateRequest(mood="romance", instruments=["piano"]), [
            {"id": "t1", "path": self.src, "created_at": "2026-11-05 13:00:00", "duration": 10,
             "caption": "c", "seed": 1, "bpm": 90, "keyscale": "C major",
             "dit_model": "turbo", "lm_model": "lm"}])

        class Runtime:
            state, message, output_dir = "ready", "ok", self.tmp.name

            def gpu_info(self):
                return None

        app = create_app(Runtime(), JobStore(lambda r, p: []), TOKEN, self.history)
        self.client = TestClient(app)

    def tearDown(self):
        self.history._conn.close()
        self.tmp.cleanup()

    def test_history_survives_reopen(self):
        reopened = HistoryStore(self.db)
        items = reopened.list()
        reopened._conn.close()
        self.assertEqual(items[0]["id"], "t1")
        self.assertEqual(items[0]["request"]["instruments"], ["piano"])
        self.assertTrue(items[0]["exists"])

    def test_history_route(self):
        items = self.client.get("/history", headers=HEADERS).json()
        self.assertEqual([i["id"] for i in items], ["t1"])

    def test_preview_writes_edited_copy_and_keeps_original(self):
        resp = self.client.post("/preview", headers=HEADERS,
                                json={"id": "t1", "edits": {"trim_start": 1, "trim_end": 4}})
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.json()["duration"], 3.0)
        self.assertAlmostEqual(sf.info(self.src).duration, 10.0)

    def test_export_mp3(self):
        sf.write(self.src, np.zeros((48000 * 3, 2), dtype=np.float32), 48000)
        dest = os.path.join(self.tmp.name, "out", "song.mp3")
        resp = self.client.post("/export", headers=HEADERS,
                                json={"id": "t1", "format": "mp3", "dest": dest,
                                      "edits": {"fade_out": 2}})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertAlmostEqual(sf.info(dest).duration, 3.0, delta=0.1)

    def test_export_failure_is_400_not_crash(self):
        dest = os.path.join(self.tmp.name, "song.mp3")
        resp = self.client.post("/export", headers=HEADERS,
                                json={"id": "t1", "format": "mp3", "dest": dest})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("MP3", resp.json()["detail"])

    def test_delete_removes_record_and_engine_files(self):
        self.client.post("/preview", headers=HEADERS, json={"id": "t1"})
        preview = os.path.join(self.tmp.name, "previews", "t1.wav")
        self.assertTrue(os.path.isfile(preview))
        resp = self.client.delete("/history/t1", headers=HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["removed_files"], 2)
        self.assertFalse(os.path.exists(self.src))
        self.assertFalse(os.path.exists(preview))
        self.assertEqual(self.client.get("/history", headers=HEADERS).json(), [])

    def test_delete_never_touches_files_outside_output_dir(self):
        with tempfile.TemporaryDirectory() as other:
            outside = os.path.join(other, "user_export.wav")
            sf.write(outside, tone(), SR)
            self.history.add_many(GenerateRequest(), [
                {"id": "ext", "path": outside, "created_at": "2026-11-05 13:00:01"}])
            resp = self.client.delete("/history/ext", headers=HEADERS)
            self.assertEqual(resp.json()["removed_files"], 0)
            self.assertTrue(os.path.isfile(outside))
        self.assertIsNone(self.history.get("ext"))

    def test_delete_unknown_track_404(self):
        self.assertEqual(self.client.delete("/history/nope", headers=HEADERS).status_code, 404)

    def test_errors_are_user_readable(self):
        missing = self.client.post("/preview", headers=HEADERS, json={"id": "nope"})
        self.assertEqual(missing.status_code, 404)
        bad = self.client.post("/preview", headers=HEADERS,
                               json={"id": "t1", "edits": {"trim_start": 9.5}})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("자르기", bad.json()["detail"])


if __name__ == "__main__":
    unittest.main()
