import { useEffect, useRef, useState, type ReactNode } from "react";
import { AudioWaveform, Pause, Play, Repeat, Volume2 } from "lucide-react";
import WaveSurfer from "wavesurfer.js";

interface Props {
  url: string | null;
  autoPlay: boolean;
  onTime?: (seconds: number) => void;
  color?: string;
  header?: ReactNode;
  footer?: ReactNode;
}

function fmt(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function Player({ url, autoPlay, onTime, color = "#818cf8", header, footer }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const loopRef = useRef(false);
  const onTimeRef = useRef(onTime);
  onTimeRef.current = onTime;
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [total, setTotal] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [loop, setLoop] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    loopRef.current = loop;
  }, [loop]);

  useEffect(() => {
    if (!box.current || !url) return;
    const w = WaveSurfer.create({
      container: box.current,
      height: 110,
      waveColor: "#3a4152",
      progressColor: color,
      cursorColor: "#e5e7eb",
      cursorWidth: 1,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      url,
    });
    w.setVolume(volume);
    setLoadError(false);
    w.on("error", () => setLoadError(true));
    w.on("ready", () => {
      setTotal(w.getDuration());
      if (autoPlay) w.play();
    });
    w.on("timeupdate", (t) => {
      setTime(t);
      onTimeRef.current?.(t);
    });
    w.on("play", () => setPlaying(true));
    w.on("pause", () => setPlaying(false));
    w.on("finish", () => {
      if (loopRef.current) {
        w.seekTo(0);
        w.play();
      }
    });
    ws.current = w;
    return () => {
      w.destroy();
      ws.current = null;
      setPlaying(false);
      setTime(0);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, color]);

  const changeVolume = (v: number) => {
    setVolume(v);
    ws.current?.setVolume(v);
  };

  if (!url) {
    return (
      <div className="card player empty">
        <AudioWaveform size={28} />
        <span>생성한 음악이 여기에 표시됩니다</span>
      </div>
    );
  }

  return (
    <div className="card player">
      {header}
      <div ref={box} className="wave" />
      {loadError && <div className="banner err">음악 파일을 불러오지 못했습니다. 파일이 삭제되었거나 이동되었을 수 있습니다.</div>}
      <div className="transport">
        <button className="play" onClick={() => ws.current?.playPause()} title="재생 / 일시정지">
          {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
        </button>
        <span className="mono time">{fmt(time)} <span className="muted">/ {fmt(total)}</span></span>
        <button className={`icon-toggle ${loop ? "on" : ""}`} onClick={() => setLoop(!loop)} title="반복 재생">
          <Repeat size={15} /> 반복 재생
        </button>
        <label className="volume" title="미리 듣기 볼륨 (저장 파일에는 영향 없음)">
          <Volume2 size={15} />
          <input type="range" min={0} max={1} step={0.01} value={volume}
            onChange={(e) => changeVolume(Number(e.target.value))} />
        </label>
      </div>
      {footer}
    </div>
  );
}
