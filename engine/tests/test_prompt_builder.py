"""Tests for instrumental caption building and vocal sanitizing."""

import unittest

from bgm_engine.prompt_builder import (
    INSTRUMENTAL_SUFFIX,
    build_lm_query,
    build_tag_caption,
    ensure_instruments,
    sanitize_caption,
)

LM_CAPTION = (
    "A gentle and romantic J-pop ballad featuring a clean, melodic piano as the primary "
    "accompaniment. A sweet, clear female vocal carries the melody with an emotional and "
    "slightly breathy delivery. The arrangement is supported by subtle synth pads."
)


class SanitizeCaptionTest(unittest.TestCase):
    """sanitize_caption must strip vocals and always end instrumental."""

    def test_drops_vocal_sentence_from_lm_prose(self):
        result = sanitize_caption(LM_CAPTION)
        self.assertNotIn("vocal", result.lower().replace(INSTRUMENTAL_SUFFIX, ""))
        self.assertIn("melodic piano", result)
        self.assertIn("synth pads", result)
        self.assertNotIn(".,", result)
        self.assertTrue(result.endswith(INSTRUMENTAL_SUFFIX))

    def test_drops_vocal_tags_from_tag_list(self):
        result = sanitize_caption("pop, female vocals, piano, choir")
        self.assertEqual(result, f"pop, piano, {INSTRUMENTAL_SUFFIX}")

    def test_empty_caption_returns_suffix_only(self):
        self.assertEqual(sanitize_caption("  "), INSTRUMENTAL_SUFFIX)

    def test_does_not_drop_words_containing_vocal_substrings(self):
        result = sanitize_caption("warm humid summer evening, rapid strings")
        self.assertIn("humid", result)
        self.assertIn("rapid strings", result)


class BuildTagCaptionTest(unittest.TestCase):
    """build_tag_caption maps UI keys to tags."""

    def test_mood_and_instruments(self):
        result = build_tag_caption("romance", ["piano", "violin"])
        self.assertIn("romantic", result)
        self.assertIn("featuring piano, violin", result)
        self.assertTrue(result.endswith(INSTRUMENTAL_SUFFIX))

    def test_ai_auto_instruments_has_no_featuring(self):
        self.assertNotIn("featuring", build_tag_caption("sad", []))

    def test_unknown_keys_raise(self):
        with self.assertRaises(ValueError):
            build_tag_caption("unknown", [])
        with self.assertRaises(ValueError):
            build_tag_caption(None, ["kazoo"])


class QueryAndInstrumentTest(unittest.TestCase):
    """LM query composition and instrument enforcement."""

    def test_query_contains_description_and_hints(self):
        query = build_lm_query("설레는 첫 만남", None, "따뜻한", ["piano"])
        self.assertTrue(query.startswith("설레는 첫 만남"))
        self.assertIn("Mood: 따뜻한", query)
        self.assertIn("Instruments: piano", query)
        self.assertIn("no vocals", query)

    def test_ensure_instruments_appends_only_missing(self):
        result = ensure_instruments("soft piano melody", ["piano", "flute"])
        self.assertEqual(result, "soft piano melody, featuring flute")


if __name__ == "__main__":
    unittest.main()
