import { AudioLines, Download, Headphones, Scissors, Undo2, Volume2 } from "lucide-react";
import type { Edits } from "../lib/engine";

interface Props {
  edits: Edits;
  duration: number;
  currentTime: number;
  disabled: boolean;
  previewing: boolean;
  onChange: (next: Edits) => void;
  onPreview: () => void;
  onReset: () => void;
  onSave: (format: "wav" | "mp3") => void;
}

const round1 = (n: number) => Math.round(n * 10) / 10;

function NumberField({ label, value, max, onChange, disabled }: {
  label: string; value: number; max: number; disabled: boolean; onChange: (v: number) => void;
}) {
  return (
    <label className="num-field">
      <span>{label}</span>
      <input type="number" min={0} max={max} step={0.1} disabled={disabled} value={value}
        onChange={(e) => onChange(Math.max(0, Number(e.target.value)))} />
      <em>초</em>
    </label>
  );
}

export function EditBar(p: Props) {
  const e = p.edits;
  const set = (patch: Partial<Edits>) => p.onChange({ ...e, ...patch });
  const end = e.trim_end ?? round1(p.duration);
  const now = round1(p.currentTime);

  return (
    <footer className={`toolbar ${p.disabled ? "disabled" : ""}`}>
      <div className="tool">
        <span className="tool-label"><Scissors size={13} /> 자르기</span>
        <NumberField label="시작" value={e.trim_start} max={p.duration} disabled={p.disabled}
          onChange={(v) => set({ trim_start: v })} />
        <button className="btn tiny" disabled={p.disabled} onClick={() => set({ trim_start: now })}
          title="재생 위치를 시작점으로">현재 위치</button>
        <NumberField label="끝" value={end} max={p.duration} disabled={p.disabled}
          onChange={(v) => set({ trim_end: v })} />
        <button className="btn tiny" disabled={p.disabled} onClick={() => set({ trim_end: now })}
          title="재생 위치를 끝점으로">현재 위치</button>
      </div>
      <div className="tool" title="소리가 갑자기 시작하거나 뚝 끊기지 않게 부드럽게 만듭니다">
        <span className="tool-label"><AudioLines size={13} /> 부드럽게</span>
        <NumberField label="서서히 시작" value={e.fade_in} max={30} disabled={p.disabled}
          onChange={(v) => set({ fade_in: Math.min(v, 30) })} />
        <NumberField label="서서히 끝내기" value={e.fade_out} max={30} disabled={p.disabled}
          onChange={(v) => set({ fade_out: Math.min(v, 30) })} />
      </div>
      <div className="tool">
        <span className="tool-label"><Volume2 size={13} /> 볼륨</span>
        <input type="range" min={-12} max={12} step={0.5} value={e.gain_db} disabled={p.disabled}
          onChange={(ev) => set({ gain_db: Number(ev.target.value) })} />
        <span className="mono db">{e.gain_db > 0 ? "+" : ""}{e.gain_db.toFixed(1)} dB</span>
      </div>
      <div className="tool end">
        <button className={`btn ghost ${p.previewing ? "active" : ""}`} disabled={p.disabled}
          onClick={p.onPreview}>
          <Headphones size={15} /> {p.previewing ? "편집본 재생 중" : "편집 미리 듣기"}
        </button>
        <button className="btn ghost" disabled={p.disabled} onClick={p.onReset} title="편집 설정 초기화">
          <Undo2 size={15} /> 원본
        </button>
        <div className="save-group">
          <button className="btn primary" disabled={p.disabled} onClick={() => p.onSave("wav")}>
            <Download size={15} /> WAV
          </button>
          <button className="btn primary" disabled={p.disabled} onClick={() => p.onSave("mp3")}>
            <Download size={15} /> MP3
          </button>
        </div>
      </div>
    </footer>
  );
}
