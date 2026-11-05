import { LoaderCircle, MessageSquareText, RefreshCw, Sparkles, Square, Wand2 } from "lucide-react";
import type { Job } from "../lib/engine";

interface Props {
  description: string;
  onDescription: (text: string) => void;
  dialogueMode: boolean;
  onDialogueMode: (on: boolean) => void;
  variations: number;
  onVariations: (n: number) => void;
  maxVariations: number;
  canGenerate: boolean;
  canRepeat: boolean;
  analyzing: boolean;
  recommendation: string | null;
  job: Job | null;
  busy: boolean;
  onAnalyze: () => void;
  onGenerate: () => void;
  onRepeat: () => void;
  onCancel: () => void;
}

export function Composer(p: Props) {
  const pct = p.job ? Math.round(p.job.progress * 100) : 0;
  return (
    <div className="card composer">
      <div className="card-head">
        <span className="card-title">음악 설명</span>
        <span className="card-hint">장면이나 느낌을 한국어로 자유롭게 · 비워 두면 왼쪽 선택만 사용</span>
      </div>
      <textarea className="desc" maxLength={1000} value={p.description}
        onChange={(e) => p.onDescription(e.target.value)}
        placeholder="예: 남자 주인공이 혼자 공원 벤치에 앉아 누군가를 떠올리는 장면. 조용하고 조금 쓸쓸하지만 따뜻한 느낌." />

      <div className="composer-tools">
        <button className="btn ghost" disabled={!p.canGenerate || p.description.trim().length < 2}
          onClick={p.onAnalyze} title="설명을 읽고 어울리는 분위기와 악기를 왼쪽에 골라 줍니다">
          {p.analyzing ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}
          AI 추천 받기
        </button>
        <label className={`toggle-pill ${p.dialogueMode ? "on" : ""}`}
          title="대사가 잘 들리도록 단순하고 잔잔하게, 목소리 대역을 비워서 만듭니다">
          <input type="checkbox" checked={p.dialogueMode}
            onChange={(e) => p.onDialogueMode(e.target.checked)} />
          <MessageSquareText size={15} /> 대사 배경음악 모드
        </label>
        <span className="count">{p.description.length} / 1000</span>
      </div>
      {p.recommendation && <div className="banner ok"><Sparkles size={14} /> {p.recommendation}</div>}

      <div className="generate-row">
        <button className="btn primary big" disabled={!p.canGenerate} onClick={p.onGenerate}>
          <Wand2 size={18} /> 음악 만들기
        </button>
        <div className="field-inline">
          <span className="label">버전 수</span>
          <div className="segmented small">
            {[1, 2, 4].map((n) => (
              <button key={n} className={p.variations === n ? "on" : ""} disabled={n > p.maxVariations}
                onClick={() => p.onVariations(n)}>
                {n}
              </button>
            ))}
          </div>
        </div>
        <button className="btn ghost" disabled={!p.canGenerate || !p.canRepeat} onClick={p.onRepeat}
          title="마지막 설정 그대로 새로 만듭니다">
          <RefreshCw size={15} /> 다시 만들기
        </button>
      </div>

      {p.busy && p.job && (
        <div className="progress">
          <LoaderCircle size={16} className="spin accent" />
          <div className="bar"><div style={{ width: `${pct}%` }} /></div>
          <span className="mono">{pct}%</span>
          <span className="muted">{p.job.message}</span>
          <button className="btn danger small" disabled={p.job.message === "취소하는 중"} onClick={p.onCancel}>
            <Square size={12} fill="currentColor" /> 취소
          </button>
        </div>
      )}
    </div>
  );
}
