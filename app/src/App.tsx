import { useCallback, useEffect, useRef, useState } from "react";
import { ask, save } from "@tauri-apps/plugin-dialog";
import { CircleAlert, CircleCheck, Info, LoaderCircle } from "lucide-react";
import "./App.css";
import { Composer } from "./components/Composer";
import { EditBar } from "./components/EditBar";
import { Header } from "./components/Header";
import { OptionsPanel, type Settings } from "./components/OptionsPanel";
import { Player } from "./components/Player";
import { ResultList } from "./components/ResultList";
import { TrackActions } from "./components/TrackActions";
import {
  NO_EDITS, analyzeScene, audioUrl, deleteTrack, exportTrack, listHistory, makeLoop, renderPreview,
  startGenerate, startVariation, type Edits, type GenerateBody, type HistoryItem, type Job,
} from "./lib/engine";
import {
  CUSTOM_MOOD, DURATION_MAX, DURATION_MIN, INSTRUMENTS, MOODS, PRESETS, labelOf,
} from "./lib/options";
import { moodColor } from "./lib/icons";
import { useEngine } from "./lib/useEngine";
import { useJobRunner, type JobOutcome } from "./lib/useJobRunner";

export interface Track extends HistoryItem {
  title: string;
}

const DEFAULT_SETTINGS: Settings = {
  mood: "romance", customMood: "", instruments: ["piano"], duration: 60, customDuration: false,
  preset: "opening", dialogueMode: false,
};
const KIND_SUFFIX: Record<Track["kind"], string> = { generated: "", variation: " (비슷한 버전)", loop: " (반복)" };

function toBody(s: Settings, description: string, variations: number): GenerateBody {
  return {
    mood: s.mood && s.mood !== CUSTOM_MOOD ? s.mood : null,
    custom_mood: s.mood === CUSTOM_MOOD ? s.customMood : "",
    instruments: s.instruments,
    duration: s.duration,
    description,
    variations,
    preset: s.preset,
    dialogue_mode: s.dialogueMode,
  };
}

function titleFor(h: HistoryItem): string {
  const b = h.request;
  const scene = b.preset ? labelOf(PRESETS, b.preset) : null;
  const mood = b.mood ? labelOf(MOODS, b.mood).split(" / ")[0] : b.custom_mood || "자유";
  const inst = b.instruments?.length
    ? b.instruments.map((k) => labelOf(INSTRUMENTS, k)).join("+")
    : "AI 악기";
  const talk = b.dialogue_mode ? " · 대사용" : "";
  return `${scene ?? mood} · ${inst}${talk}${KIND_SUFFIX[h.kind ?? "generated"]}`;
}

function safeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|#()]/g, "").replace(/\s*·\s*/g, "_").replace(/\s+/g, "_");
}

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function App() {
  const engine = useEngine();
  const runner = useJobRunner();
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [description, setDescription] = useState("");
  const [variations, setVariations] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [edits, setEdits] = useState<Edits>(NO_EDITS);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [working, setWorking] = useState(false);
  const lastBody = useRef<GenerateBody | null>(null);

  const ready = engine.phase === "ready";
  const selected = tracks.find((t) => t.id === selectedId) ?? null;
  const maxDuration = engine.limits?.max_duration ?? DURATION_MAX;
  const maxVariations = engine.limits?.max_variations ?? 4;
  const durationOk = settings.duration >= DURATION_MIN && settings.duration <= maxDuration;
  const variationsOk = variations <= maxVariations;
  const idle = ready && !runner.busy && !analyzing && !working;

  const refreshHistory = useCallback(async () => {
    setTracks((await listHistory()).map((h) => ({ ...h, title: titleFor(h) })));
  }, []);

  useEffect(() => {
    if (ready) refreshHistory().catch((e) => setError(errText(e)));
  }, [ready, refreshHistory]);

  function select(id: string | null) {
    setSelectedId(id);
    setEdits(NO_EDITS);
    setPreviewUrl(null);
    setCurrentTime(0);
  }

  function changeEdits(next: Edits) {
    setEdits(next);
    setPreviewUrl(null);
  }

  async function finish(outcome: JobOutcome) {
    if (outcome.kind === "failed") setError(outcome.error);
    if (outcome.kind === "cancelled") setNotice("생성을 취소했습니다.");
    if (outcome.kind !== "done") return;
    await refreshHistory();
    select(outcome.results[0]?.id ?? null);
  }

  async function startJob(start: () => Promise<Job>) {
    setError(null);
    setNotice(null);
    await finish(await runner.run(start));
  }

  function generate(body: GenerateBody) {
    lastBody.current = body;
    return startJob(() => startGenerate(body));
  }

  async function analyze() {
    setError(null);
    setAnalyzing(true);
    try {
      const rec = await analyzeScene(description);
      setSettings((s) => ({
        ...s, mood: rec.mood ?? s.mood, instruments: rec.instruments.length ? rec.instruments : [],
      }));
      const mood = rec.mood ? labelOf(MOODS, rec.mood) : "자유";
      const inst = rec.instruments.map((k) => labelOf(INSTRUMENTS, k)).join(", ") || "AI 자동 선택";
      setRecommendation(`추천: 분위기 '${mood}', 악기 '${inst}' — 왼쪽에 적용했어요. 바꿔도 됩니다.`);
    } catch (e) {
      setError(errText(e));
    } finally {
      setAnalyzing(false);
    }
  }

  async function loop(repeatTo: number | null) {
    if (!selected) return;
    setError(null);
    setWorking(true);
    try {
      const made = await makeLoop(selected.id, repeatTo);
      await refreshHistory();
      select(made.id);
      setNotice(`반복 음악을 만들었습니다 (반복 단위 ${made.loop_seconds}초). 🔁 반복 재생으로 이음새를 들어보세요.`);
    } catch (e) {
      setError(errText(e));
    } finally {
      setWorking(false);
    }
  }

  async function remove(track: Track) {
    const ok = await ask(
      `"${track.title}"을(를) 삭제할까요?

앱에 보관된 원본 음원도 함께 지워집니다.
WAV/MP3로 따로 저장한 파일은 지워지지 않습니다.`,
      { title: "음악 삭제", kind: "warning", okLabel: "삭제", cancelLabel: "취소" },
    );
    if (!ok) return;
    setError(null);
    try {
      await deleteTrack(track.id);
      if (track.id === selectedId) select(null);
      await refreshHistory();
      setNotice(`삭제했습니다: ${track.title}`);
    } catch (e) {
      setError(errText(e));
    }
  }

  async function preview() {
    if (!selected) return;
    setError(null);
    try {
      const r = await renderPreview(selected.id, edits);
      setPreviewUrl(`${audioUrl(r.path)}&v=${Date.now()}`);
    } catch (e) {
      setError(errText(e));
    }
  }

  async function saveAs(format: "wav" | "mp3") {
    if (!selected) return;
    setError(null);
    const stamp = selected.created_at.replace(/[-: ]/g, "").slice(0, 12);
    const dest = await save({
      defaultPath: `${safeFileName(selected.title)}_${stamp}.${format}`,
      filters: [{ name: `${format.toUpperCase()} 오디오`, extensions: [format] }],
    });
    if (!dest) return;
    const path = dest.toLowerCase().endsWith(`.${format}`) ? dest : `${dest}.${format}`;
    try {
      await exportTrack(selected.id, format, path, edits);
      setNotice(`저장했습니다: ${path}`);
    } catch (e) {
      setError(errText(e));
    }
  }

  const playerUrl = previewUrl ?? (selected ? audioUrl(selected.path) : null);

  return (
    <div className="app">
      <Header engine={engine} />
      {engine.phase === "error" && (
        <div className="banner err global">
          <CircleAlert size={15} /> {engine.message}
          {engine.logFile && <small className="muted"> 로그: {engine.logFile}</small>}
        </div>
      )}
      <main className="body">
        <OptionsPanel value={settings} onChange={setSettings} maxDuration={maxDuration} />

        <section className="panel center">
          <Composer description={description} onDescription={setDescription}
            dialogueMode={settings.dialogueMode}
            onDialogueMode={(on) => setSettings((s) => ({ ...s, dialogueMode: on }))}
            variations={variations} onVariations={setVariations} maxVariations={maxVariations}
            canGenerate={idle && durationOk && variationsOk} canRepeat={lastBody.current !== null}
            analyzing={analyzing} recommendation={recommendation}
            job={runner.job} busy={runner.busy}
            onAnalyze={analyze}
            onGenerate={() => generate(toBody(settings, description, variations))}
            onRepeat={() => lastBody.current && generate(lastBody.current)}
            onCancel={runner.cancel} />

          {!ready && engine.phase !== "error" && (
            <div className="banner info"><LoaderCircle size={14} className="spin" />
              AI 모델을 불러오는 중입니다. 처음 실행은 1분 정도 걸립니다.</div>
          )}
          {!durationOk && (
            <div className="banner err"><CircleAlert size={14} />
              길이는 {DURATION_MIN}~{maxDuration}초로 입력해 주세요.
              {maxDuration < DURATION_MAX && " (이 그래픽카드의 최대 길이)"}</div>
          )}
          {error && <div className="banner err"><CircleAlert size={14} /> {error}</div>}
          {notice && <div className="banner ok"><CircleCheck size={14} /> {notice}</div>}

          <Player url={playerUrl} autoPlay onTime={setCurrentTime}
            color={moodColor(selected?.request.mood)}
            header={selected && (
              <div className="player-head">
                <span className="swatch" style={{ background: moodColor(selected.request.mood) }} />
                <span className="player-title">{selected.title}</span>
                {previewUrl && <span className="tag accent">편집본</span>}
                <span className="tags">
                  {selected.bpm && <span className="tag">{selected.bpm} BPM</span>}
                  {selected.keyscale && <span className="tag">{selected.keyscale}</span>}
                  <span className="tag">{Math.round(selected.duration)}초</span>
                </span>
              </div>
            )}
            footer={selected && (
              <>
                <TrackActions disabled={!idle}
                  onVariation={() => startJob(() => startVariation(selected.id))}
                  onLoop={loop} />
                <details className="info">
                  <summary><Info size={13} /> 곡 정보</summary>
                  <dl>
                    <dt>생성 날짜</dt><dd className="mono">{selected.created_at}</dd>
                    <dt>AI 프롬프트</dt><dd>{selected.caption}</dd>
                    {selected.request.description && <><dt>입력한 설명</dt><dd>{selected.request.description}</dd></>}
                    <dt>시드</dt><dd className="mono">{selected.seed ?? "-"}</dd>
                    <dt>모델</dt><dd className="mono">{selected.dit_model} + {selected.lm_model}</dd>
                  </dl>
                </details>
              </>
            )} />
        </section>

        <ResultList tracks={tracks} selectedId={selectedId} onSelect={select}
          canDelete={idle} onDelete={remove} />
      </main>

      <EditBar edits={edits} duration={selected?.duration ?? 0} currentTime={currentTime}
        disabled={!selected || !ready} previewing={previewUrl !== null}
        onChange={changeEdits} onPreview={preview} onReset={() => changeEdits(NO_EDITS)}
        onSave={saveAs} />
    </div>
  );
}
