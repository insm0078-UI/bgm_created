import type { CSSProperties } from "react";
import { Clapperboard, Clock, Palette, SlidersHorizontal } from "lucide-react";
import { INSTRUMENT_ICONS, MOOD_COLORS, MOOD_ICONS, PRESET_ICONS } from "../lib/icons";
import {
  CUSTOM_MOOD, DURATIONS, DURATION_MIN, INSTRUMENTS, MOODS, PRESETS,
} from "../lib/options";
import { Section } from "./Section";

export interface Settings {
  mood: string | null;
  customMood: string;
  instruments: string[];
  duration: number;
  customDuration: boolean;
  preset: string | null;
  dialogueMode: boolean;
}

interface Props {
  value: Settings;
  onChange: (next: Settings) => void;
  /** Longest track this GPU can generate (from the engine), in seconds. */
  maxDuration: number;
}

const moodStyle = (key: string) => ({ "--chip": MOOD_COLORS[key] }) as CSSProperties;

export function OptionsPanel({ value, onChange, maxDuration }: Props) {
  const set = (patch: Partial<Settings>) => onChange({ ...value, ...patch });
  const toggleInstrument = (key: string) => {
    const has = value.instruments.includes(key);
    set({ instruments: has ? value.instruments.filter((k) => k !== key) : [...value.instruments, key] });
  };
  const AutoIcon = INSTRUMENT_ICONS.auto;
  const CustomIcon = MOOD_ICONS.custom;

  return (
    <aside className="panel left">
      <Section tone="preset" icon={Clapperboard} title="장면 프리셋" hint="장면에 맞는 편곡을 더해 줍니다">
        <div className="preset-grid">
          {PRESETS.map((p) => {
            const Icon = PRESET_ICONS[p.key];
            return (
              <button key={p.key} className={`preset ${value.preset === p.key ? "on" : ""}`}
                onClick={() => set({ preset: value.preset === p.key ? null : p.key })}>
                <Icon size={16} />
                <span>{p.label}</span>
              </button>
            );
          })}
        </div>
      </Section>

      <Section tone="mood" icon={Palette} title="음악 분위기">
        <div className="chips">
          {MOODS.map((m) => {
            const Icon = MOOD_ICONS[m.key];
            return (
              <button key={m.key} style={moodStyle(m.key)}
                className={`chip mood ${value.mood === m.key ? "on" : ""}`}
                onClick={() => set({ mood: value.mood === m.key ? null : m.key })}>
                <Icon size={14} /> {m.label}
              </button>
            );
          })}
          <button style={moodStyle("custom")}
            className={`chip mood ${value.mood === CUSTOM_MOOD ? "on" : ""}`}
            onClick={() => set({ mood: value.mood === CUSTOM_MOOD ? null : CUSTOM_MOOD })}>
            <CustomIcon size={14} /> 직접 입력
          </button>
        </div>
        {value.mood === CUSTOM_MOOD && (
          <input className="text" placeholder="예: 비 오는 날 카페처럼 차분한" maxLength={200}
            value={value.customMood} onChange={(e) => set({ customMood: e.target.value })} />
        )}
      </Section>

      <Section tone="instrument" icon={SlidersHorizontal} title="악기" hint="여러 개 선택 가능">
        <div className="chips">
          <button className={`chip inst ${value.instruments.length === 0 ? "on" : ""}`}
            onClick={() => set({ instruments: [] })}>
            <AutoIcon size={14} /> AI 자동 선택
          </button>
          {INSTRUMENTS.map((i) => {
            const Icon = INSTRUMENT_ICONS[i.key];
            return (
              <button key={i.key} className={`chip inst ${value.instruments.includes(i.key) ? "on" : ""}`}
                onClick={() => toggleInstrument(i.key)}>
                <Icon size={14} /> {i.label}
              </button>
            );
          })}
        </div>
      </Section>

      <Section tone="duration" icon={Clock} title="음악 길이">
        <div className="segmented">
          {DURATIONS.map((d) => (
            <button key={d} className={!value.customDuration && value.duration === d ? "on" : ""}
              disabled={d > maxDuration} title={d > maxDuration ? "이 그래픽카드에서는 만들 수 없는 길이입니다" : undefined}
              onClick={() => set({ duration: d, customDuration: false })}>
              {d < 60 ? `${d}초` : `${d / 60}분`}
            </button>
          ))}
          <button className={value.customDuration ? "on" : ""} onClick={() => set({ customDuration: true })}>
            직접
          </button>
        </div>
        {value.customDuration && (
          <label className="inline">
            <input className="text num" type="number" min={DURATION_MIN} max={maxDuration}
              value={value.duration} onChange={(e) => set({ duration: Number(e.target.value) })} />
            초 <span className="muted">({DURATION_MIN}~{maxDuration}초)</span>
          </label>
        )}
      </Section>
    </aside>
  );
}
