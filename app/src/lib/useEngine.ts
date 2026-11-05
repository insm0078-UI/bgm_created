// Polls engine process status and /health so the header always shows AI/GPU state.

import { useEffect, useState } from "react";
import { engineStatus, health, type GpuInfo, type Limits } from "./engine";

export type EnginePhase = "starting" | "loading" | "ready" | "error";

export interface EngineView {
  phase: EnginePhase;
  message: string;
  gpu: GpuInfo | null;
  logFile: string | null;
  limits: Limits | null;
}

const INITIAL: EngineView = {
  phase: "starting", message: "AI 엔진 시작 중", gpu: null, logFile: null, limits: null,
};

export function useEngine(): EngineView {
  const [view, setView] = useState<EngineView>(INITIAL);

  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const status = await engineStatus();
        const logFile = status.info?.log_file ?? null;
        if (status.start_error) {
          setView({ ...INITIAL, phase: "error", message: status.start_error, logFile });
          return;
        }
        if (status.exited !== null) {
          setView({ ...INITIAL, phase: "error", message: "AI 엔진이 예기치 않게 종료되었습니다.", logFile });
          return;
        }
        try {
          const h = await health();
          setView({
            phase: h.state === "ready" ? "ready" : h.state, message: h.message, gpu: h.gpu, logFile,
            limits: h.limits ?? null,
          });
        } catch {
          setView({ ...INITIAL, logFile });
        }
      } finally {
        if (!stopped) timer = window.setTimeout(tick, 2000);
      }
    };
    let timer = window.setTimeout(tick, 300);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, []);

  return view;
}
