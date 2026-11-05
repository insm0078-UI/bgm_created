// Korean UI labels mapped to engine keys (see engine/bgm_engine/prompt_builder.py).

export interface Option {
  key: string;
  label: string;
}

export const MOODS: Option[] = [
  { key: "romance", label: "로맨스 / 설렘" },
  { key: "sad", label: "슬픔 / 이별" },
  { key: "daily", label: "밝은 일상" },
  { key: "comedy", label: "코미디 / 귀여움" },
  { key: "tension", label: "긴장 / 미스터리" },
  { key: "hope", label: "감동 / 희망" },
  { key: "peaceful", label: "평화로운 휴식" },
  { key: "dreamy", label: "몽환적인 분위기" },
];

export const CUSTOM_MOOD = "custom";

export const INSTRUMENTS: Option[] = [
  { key: "piano", label: "피아노" },
  { key: "acoustic_guitar", label: "어쿠스틱 기타" },
  { key: "violin", label: "바이올린" },
  { key: "strings", label: "현악기" },
  { key: "music_box", label: "오르골" },
  { key: "flute", label: "플루트" },
  { key: "jazz", label: "재즈 악기" },
  { key: "ensemble", label: "여러 악기 조합" },
];

export const DURATIONS = [15, 30, 60, 120, 180];
export const DURATION_MIN = 10;
export const DURATION_MAX = 600;

// Keep keys in sync with engine/bgm_engine/scene.py PRESETS.
export const PRESETS: Option[] = [
  { key: "opening", label: "오프닝" },
  { key: "daily_talk", label: "일상 대화" },
  { key: "romance", label: "로맨스 장면" },
  { key: "comedy", label: "코미디 장면" },
  { key: "sad", label: "슬픈 장면" },
  { key: "tension", label: "긴장 장면" },
  { key: "ending", label: "엔딩" },
];

export const LOOP_TARGETS: { value: number | null; label: string }[] = [
  { value: null, label: "한 번 (반복용 조각)" },
  { value: 60, label: "1분으로 늘리기" },
  { value: 180, label: "3분으로 늘리기" },
  { value: 300, label: "5분으로 늘리기" },
];

export function labelOf(list: Option[], key: string): string {
  return list.find((o) => o.key === key)?.label ?? key;
}
