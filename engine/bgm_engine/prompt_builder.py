"""Turn UI selections (mood, instruments) into an instrumental-only ACE-Step caption.

ACE-Step's LM sometimes adds vocals to captions even when asked for instrumental
music, so every caption passes through ``sanitize_caption`` before generation.
"""

import re

MOOD_TAGS: dict[str, str] = {
    "romance": "romantic, heart-fluttering, warm, tender",
    "sad": "sad, melancholic, farewell, emotional",
    "daily": "bright, cheerful, slice-of-life, light and easy",
    "comedy": "comedic, cute, playful, bouncy",
    "tension": "tense, suspenseful, mysterious, dark",
    "hope": "touching, hopeful, uplifting, inspiring",
    "peaceful": "peaceful, calm, relaxing, soothing",
    "dreamy": "dreamy, ethereal, floating, ambient",
}

INSTRUMENT_TAGS: dict[str, str] = {
    "piano": "piano",
    "acoustic_guitar": "acoustic guitar",
    "violin": "violin",
    "strings": "string ensemble",
    "music_box": "music box",
    "flute": "flute",
    "jazz": "jazz band with upright bass, brushed drums and saxophone",
    "ensemble": "rich ensemble of multiple instruments",
}

BASE_TAGS = "instrumental background music, soundtrack"
INSTRUMENTAL_SUFFIX = "instrumental, no vocals, no singing"

_VOCAL_WORDS = re.compile(
    r"\b(vocals?|vocalists?|voices?|sing(s|ing|er|ers)?|sung|lyrics?|choir|choral|rap(s|ping)?"
    r"|hum(s|ming)?|chant(s|ing)?|duet|a cappella)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def sanitize_caption(caption: str, extra: str = "") -> str:
    """Remove vocal references from a caption and force the instrumental suffix.

    Args:
        caption: Caption text, possibly LM-generated prose or comma-separated tags.
        extra: Optional tags (scene preset / dialogue mode) inserted before the suffix.

    Returns:
        Caption with vocal-related sentences/tags dropped and the instrumental suffix appended.
    """
    sentences = _SENTENCE_SPLIT.split(caption.strip())
    kept_sentences = []
    for sentence in sentences:
        if "," in sentence and not sentence.rstrip().endswith((".", "!", "?")):
            tags = [t.strip() for t in sentence.split(",")]
            sentence = ", ".join(t for t in tags if t and not _VOCAL_WORDS.search(t))
        elif _VOCAL_WORDS.search(sentence):
            continue
        if sentence:
            kept_sentences.append(sentence)
    cleaned = " ".join(kept_sentences).strip().rstrip(",. ")
    parts = [p for p in (cleaned, extra.strip().strip(","), INSTRUMENTAL_SUFFIX) if p]
    return ", ".join(parts)


def build_tag_caption(mood: str | None, instruments: list[str], extra: str = "") -> str:
    """Build a tag caption from preset mood and instrument keys.

    Args:
        mood: Key from ``MOOD_TAGS`` or None (custom/unspecified).
        instruments: Keys from ``INSTRUMENT_TAGS``; empty means "let AI choose".
        extra: Optional scene/dialogue tags.

    Returns:
        Comma-separated caption ending with the instrumental suffix.

    Raises:
        ValueError: If a mood or instrument key is unknown.
    """
    parts = [BASE_TAGS]
    if mood:
        if mood not in MOOD_TAGS:
            raise ValueError(f"unknown mood: {mood}")
        parts.append(MOOD_TAGS[mood])
    unknown = [i for i in instruments if i not in INSTRUMENT_TAGS]
    if unknown:
        raise ValueError(f"unknown instruments: {unknown}")
    if instruments:
        parts.append("featuring " + ", ".join(INSTRUMENT_TAGS[i] for i in instruments))
    return sanitize_caption(", ".join(parts), extra)


def build_lm_query(description: str, mood: str | None, custom_mood: str,
                   instruments: list[str]) -> str:
    """Compose the natural-language query sent to the LM for free-text descriptions.

    Args:
        description: User's description (Korean allowed).
        mood: Preset mood key or None.
        custom_mood: User-typed mood text (used when no preset mood is chosen).
        instruments: Instrument keys the result must feature.

    Returns:
        Query string that asks for instrumental BGM with the given hints.
    """
    hints = []
    if mood:
        hints.append(f"Mood: {MOOD_TAGS[mood]}")
    elif custom_mood.strip():
        hints.append(f"Mood: {custom_mood.strip()}")
    if instruments:
        hints.append("Instruments: " + ", ".join(INSTRUMENT_TAGS[i] for i in instruments))
    hints.append("Instrumental background music only, no vocals.")
    return "\n".join([description.strip(), *hints])


def ensure_instruments(caption: str, instruments: list[str]) -> str:
    """Append any selected instruments the caption does not already mention.

    Args:
        caption: Sanitized caption.
        instruments: Instrument keys selected by the user.

    Returns:
        Caption guaranteed to name every selected instrument.
    """
    lowered = caption.lower()
    missing = [INSTRUMENT_TAGS[i] for i in instruments if INSTRUMENT_TAGS[i] not in lowered]
    if not missing:
        return caption
    return f"{caption}, featuring {', '.join(missing)}"
