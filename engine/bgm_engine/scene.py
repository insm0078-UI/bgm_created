"""Anime scene presets, dialogue-friendly tags, and mood/instrument recommendation."""

import re

from bgm_engine.korean_keywords import KO_INSTRUMENT_WORDS, KO_MOOD_WORDS, KO_WEIGHT, korean_scores

DIALOGUE_TAGS = (
    "soft underscore for dialogue, sparse arrangement, low dynamics, mellow, "
    "no prominent lead melody, simple and unobtrusive"
)


# Scene presets only add arrangement/feel tags. They never pick mood, instruments, or
# length — those stay the user's choice — so the tags avoid naming instruments.
PRESETS: dict[str, str] = {
    "opening": "anime opening feel, energetic build-up, memorable bright melody",
    "daily_talk": "light everyday background, relaxed groove",
    "romance": "tender romantic scene underscore, warm harmonies",
    "comedy": "comical, bouncy rhythm, playful staccato accents",
    "sad": "slow tempo, emotional, sparse and intimate",
    "tension": "low drones, suspenseful pulses, building tension",
    "ending": "warm ending credits feel, nostalgic resolution",
}

_MOOD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "romance": ("romantic", "romance", "love", "tender", "heart"),
    "sad": ("sad", "melanchol", "sorrow", "lonely", "loneliness", "bittersweet", "farewell",
            "nostalg", "longing"),
    "daily": ("cheerful", "bright", "slice-of-life", "everyday", "upbeat", "happy", "sunny"),
    "comedy": ("comedic", "comical", "playful", "quirky", "cute", "whimsical", "bouncy", "funny"),
    "tension": ("tense", "tension", "suspense", "mysterious", "mystery", "ominous", "eerie",
                "dark", "thriller"),
    "hope": ("hopeful", "uplifting", "inspiring", "triumphant", "touching", "heartwarming"),
    "peaceful": ("peaceful", "calm", "relaxing", "serene", "soothing", "tranquil", "quiet"),
    "dreamy": ("dreamy", "ethereal", "ambient", "floating", "atmospheric", "magical"),
}

_INSTRUMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "piano": ("piano",),
    "acoustic_guitar": ("acoustic guitar", "guitar", "fingerpick"),
    "violin": ("violin",),
    "strings": ("strings", "string ensemble", "orchestra", "orchestral", "cello"),
    "music_box": ("music box", "celesta", "glockenspiel"),
    "flute": ("flute",),
    "jazz": ("jazz", "saxophone", "upright bass", "brushed"),
}
MAX_RECOMMENDED_INSTRUMENTS = 3


def _count_hits(text: str, words: tuple[str, ...]) -> int:
    return sum(len(re.findall(r"\b" + re.escape(w), text)) for w in words)


def recommend(caption: str, scene: str = "") -> dict[str, object]:
    """Pick the best-matching mood and up to three instruments.

    Args:
        caption: English caption produced by the LM for a scene description.
        scene: The user's original (Korean) text; its keywords weigh ``KO_WEIGHT`` each.

    Returns:
        ``{"mood": key or None, "instruments": [keys]}`` ordered by relevance.
    """
    text = caption.lower()
    ko_mood = korean_scores(scene, KO_MOOD_WORDS)
    ko_inst = korean_scores(scene, KO_INSTRUMENT_WORDS)
    mood_scores = {m: _count_hits(text, w) + KO_WEIGHT * ko_mood[m]
                   for m, w in _MOOD_KEYWORDS.items()}
    best_mood = max(mood_scores, key=lambda m: mood_scores[m])
    inst_scores = {i: _count_hits(text, w) + KO_WEIGHT * ko_inst[i]
                   for i, w in _INSTRUMENT_KEYWORDS.items()}
    ranked = sorted((i for i, s in inst_scores.items() if s > 0), key=lambda i: -inst_scores[i])
    return {
        "mood": best_mood if mood_scores[best_mood] > 0 else None,
        "instruments": ranked[:MAX_RECOMMENDED_INSTRUMENTS],
    }


def extra_tags(preset: str | None, dialogue_mode: bool) -> str:
    """Return additional caption tags for a scene preset and/or dialogue mode.

    Raises:
        ValueError: If ``preset`` is not a known key.
    """
    parts = []
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset: {preset}")
        parts.append(PRESETS[preset])
    if dialogue_mode:
        parts.append(DIALOGUE_TAGS)
    return ", ".join(parts)
