import { useState } from "react";
import { Infinity as LoopIcon, Shuffle } from "lucide-react";
import { LOOP_TARGETS } from "../lib/options";

interface Props {
  disabled: boolean;
  onVariation: () => void;
  onLoop: (repeatTo: number | null) => void;
}

export function TrackActions({ disabled, onVariation, onLoop }: Props) {
  const [target, setTarget] = useState<number | null>(null);
  return (
    <div className="track-actions">
      <button className="btn ghost" disabled={disabled} onClick={onVariation}
        title="지금 곡의 분위기를 유지하면서 새로운 버전을 만듭니다">
        <Shuffle size={15} /> 비슷한 버전 만들기
      </button>
      <div className="split">
        <button className="btn ghost" disabled={disabled} onClick={() => onLoop(target)}
          title="끝과 처음이 자연스럽게 이어지는 반복 음악을 만듭니다">
          <LoopIcon size={15} /> 반복 음악 만들기
        </button>
        <select value={target ?? ""} disabled={disabled}
          onChange={(e) => setTarget(e.target.value ? Number(e.target.value) : null)}>
          {LOOP_TARGETS.map((t) => (
            <option key={t.label} value={t.value ?? ""}>{t.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
