import { AudioWaveform, Cpu } from "lucide-react";
import type { EngineView } from "../lib/useEngine";

const STATE: Record<EngineView["phase"], { cls: string; label: string }> = {
  starting: { cls: "wait", label: "AI 엔진 시작 중" },
  loading: { cls: "wait", label: "AI 모델 불러오는 중" },
  ready: { cls: "ok", label: "AI 준비 완료" },
  error: { cls: "err", label: "AI 오류" },
};

export function Header({ engine }: { engine: EngineView }) {
  const gpu = engine.gpu;
  const state = STATE[engine.phase];
  const usage = gpu ? Math.min(1, gpu.used_gb / gpu.total_gb) : 0;
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-mark"><AudioWaveform size={18} strokeWidth={2.4} /></span>
        <span className="brand-name">AI BGM <b>STUDIO</b></span>
      </div>
      <div className="status">
        <span className={`pill ${state.cls}`} title={engine.message}>
          <span className="dot" /> {state.label}
        </span>
        {gpu && (
          <span className="pill gpu" title={gpu.name}>
            <Cpu size={13} />
            <span className="meter"><span style={{ width: `${usage * 100}%` }} /></span>
            <span className="mono">{gpu.used_gb.toFixed(1)} / {gpu.total_gb.toFixed(0)} GB</span>
          </span>
        )}
      </div>
    </header>
  );
}
