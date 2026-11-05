// Thin client for the local AI engine (bgm_engine) started by the Tauri shell.

import { invoke } from "@tauri-apps/api/core";

export interface EngineInfo {
  port: number;
  token: string;
  log_file: string;
  output_dir: string;
}

export interface EngineStatus {
  info: EngineInfo | null;
  exited: number | null;
  start_error: string | null;
}

export interface GpuInfo {
  name: string;
  total_gb: number;
  used_gb: number;
}

export interface Limits {
  max_duration: number;
  max_variations: number;
}

export interface Health {
  state: "loading" | "ready" | "error";
  message: string;
  gpu: GpuInfo | null;
  limits?: Limits;
}

export interface TrackResult {
  id: string;
  path: string;
  duration: number;
  caption: string;
  seed: number | null;
  bpm: number | null;
  keyscale: string | null;
  dit_model: string;
  lm_model: string;
  created_at: string;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  progress: number;
  message: string;
  results: TrackResult[];
  error: string | null;
}

export interface GenerateBody {
  mood: string | null;
  custom_mood: string;
  instruments: string[];
  duration: number;
  description: string;
  variations: number;
  seed?: number;
  preset?: string | null;
  dialogue_mode?: boolean;
}

let info: EngineInfo | null = null;

export async function engineStatus(): Promise<EngineStatus> {
  const status = await invoke<EngineStatus>("engine_status");
  info = status.info;
  return status;
}

function base(): string {
  if (!info) throw new Error("AI 엔진 연결 정보가 없습니다.");
  return `http://127.0.0.1:${info.port}`;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${base()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Engine-Token": info!.token },
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(typeof detail.detail === "string" ? detail.detail : `요청 실패 (${resp.status})`);
  }
  return resp.json() as Promise<T>;
}

export const health = () => call<Health>("/health");

export const startGenerate = (body: GenerateBody) =>
  call<Job>("/generate", { method: "POST", body: JSON.stringify(body) });

export const getJob = (id: string) => call<Job>(`/jobs/${id}`);

export function audioUrl(path: string): string {
  return `${base()}/audio?path=${encodeURIComponent(path)}&t=${info!.token}`;
}

export interface HistoryItem extends TrackResult {
  request: GenerateBody;
  exists: boolean;
  kind: "generated" | "variation" | "loop";
  parent_id: string | null;
}

export interface Recommendation {
  mood: string | null;
  instruments: string[];
  caption: string;
  bpm: number | null;
}

export const cancelJob = (id: string) => call<Job>(`/jobs/${id}/cancel`, { method: "POST" });

export const analyzeScene = (scene: string) =>
  call<Recommendation>("/analyze", { method: "POST", body: JSON.stringify({ scene }) });

export const startVariation = (id: string, similarity = 0.5) =>
  call<Job>("/variation", { method: "POST", body: JSON.stringify({ id, similarity }) });

export const makeLoop = (id: string, repeatTo: number | null) =>
  call<HistoryItem & { loop_seconds: number }>("/loop", {
    method: "POST",
    body: JSON.stringify({ id, repeat_to: repeatTo }),
  });

export interface Edits {
  trim_start: number;
  trim_end: number | null;
  fade_in: number;
  fade_out: number;
  gain_db: number;
}

export const NO_EDITS: Edits = { trim_start: 0, trim_end: null, fade_in: 0, fade_out: 0, gain_db: 0 };

export const listHistory = () => call<HistoryItem[]>("/history");

export const deleteTrack = (id: string) =>
  call<{ id: string; removed_files: number }>(`/history/${id}`, { method: "DELETE" });

export const renderPreview = (id: string, edits: Edits) =>
  call<{ path: string; duration: number }>("/preview", {
    method: "POST",
    body: JSON.stringify({ id, edits }),
  });

export const exportTrack = (id: string, format: "wav" | "mp3", dest: string, edits: Edits) =>
  call<{ path: string; duration: number }>("/export", {
    method: "POST",
    body: JSON.stringify({ id, format, dest, edits }),
  });
