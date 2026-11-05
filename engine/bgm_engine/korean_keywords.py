"""Korean scene words -> mood/instrument keys.

The music LM often misreads Korean *scene* descriptions (situations without musical words),
so recommendations combine these direct keyword hits with the LM caption.
"""

KO_MOOD_WORDS: dict[str, tuple[str, ...]] = {
    "romance": ("설레", "사랑", "고백", "로맨", "첫 만남", "데이트", "두근", "연인", "키스", "좋아하"),
    "sad": ("슬프", "슬픈", "쓸쓸", "이별", "눈물", "울", "그리워", "그리움", "외로", "상실", "헤어",
            "추억", "떠올리"),
    "daily": ("일상", "아침", "학교", "등교", "출근", "산책", "밝은", "평범", "카페", "쇼핑"),
    "comedy": ("웃", "장난", "코미디", "귀여", "개그", "엉뚱", "시끌벅적", "우당탕", "황당", "익살"),
    "tension": ("긴장", "무서", "공포", "어두운", "어둠", "발소리", "뒤따라", "쫓", "미스터리", "수상",
                "위험", "불안", "범인", "추격", "비밀", "으스스", "소름"),
    "hope": ("희망", "감동", "용기", "다짐", "결심", "승리", "성공", "벅찬", "일어서", "응원", "꿈을 이루"),
    "peaceful": ("평화", "휴식", "잔잔", "조용", "고요", "편안", "여유", "햇살", "낮잠", "바람"),
    "dreamy": ("몽환", "꿈속", "환상", "신비", "별빛", "마법", "동화", "우주", "안개"),
}

KO_INSTRUMENT_WORDS: dict[str, tuple[str, ...]] = {
    "piano": ("피아노",),
    "acoustic_guitar": ("기타",),
    "violin": ("바이올린",),
    "strings": ("현악", "오케스트라", "첼로"),
    "music_box": ("오르골",),
    "flute": ("플루트", "피리"),
    "jazz": ("재즈", "색소폰"),
}

KO_WEIGHT = 3  # one Korean hit outweighs a few incidental English caption adjectives


def korean_scores(text: str, table: dict[str, tuple[str, ...]]) -> dict[str, int]:
    """Count keyword occurrences per key in Korean ``text``."""
    return {key: sum(text.count(w) for w in words) for key, words in table.items()}


def korean_mood(text: str) -> str | None:
    """Return the strongest Korean mood hint, or None when no scene words match."""
    scores = korean_scores(text, KO_MOOD_WORDS)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else None


def mood_hint(mood: str | None, custom_mood: str, description: str) -> str | None:
    """Return the preset mood key to pin, honoring the user's explicit choice first.

    Order: selected preset mood > user-typed custom mood (returns None so the custom text
    is used instead) > mood detected from Korean scene words in the description.
    """
    if mood:
        return mood
    if custom_mood.strip():
        return None
    return korean_mood(description)
