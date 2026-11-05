import type { CSSProperties } from "react";
import { Infinity as LoopIcon, ListMusic, Music, Shuffle, Trash2 } from "lucide-react";
import type { Track } from "../App";
import { moodColor } from "../lib/icons";

interface Props {
  tracks: Track[];
  selectedId: string | null;
  canDelete: boolean;
  onSelect: (id: string) => void;
  onDelete: (track: Track) => void;
}

const KIND_ICON = { generated: Music, variation: Shuffle, loop: LoopIcon };

function fmtDuration(sec: number): string {
  const s = Math.round(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function ResultList({ tracks, selectedId, canDelete, onSelect, onDelete }: Props) {
  return (
    <aside className="panel right">
      <header className="list-head">
        <ListMusic size={15} />
        <span>라이브러리</span>
        <span className="badge">{tracks.length}</span>
      </header>
      {tracks.length === 0 && <p className="empty-note">아직 만든 음악이 없습니다.</p>}
      <ul className="tracks">
        {tracks.map((t) => {
          const Icon = KIND_ICON[t.kind ?? "generated"];
          return (
            <li key={t.id} style={{ "--stripe": moodColor(t.request.mood) } as CSSProperties}
              className={`${t.id === selectedId ? "on" : ""} ${t.exists ? "" : "missing"}`}
              onClick={() => t.exists && onSelect(t.id)}
              title={t.exists ? t.caption : "원본 파일이 삭제되었습니다"}>
              <Icon size={14} className="kind" />
              <div className="body">
                <div className="name">{t.title}</div>
                <div className="meta mono">
                  {fmtDuration(t.duration)} · {t.created_at.slice(5, 16).replace("-", "/")}
                  {t.bpm ? ` · ${t.bpm} BPM` : ""}
                  {!t.exists && " · 파일 없음"}
                </div>
              </div>
              <button className="delete" disabled={!canDelete}
                title={canDelete ? "목록에서 삭제" : "생성 중에는 삭제할 수 없습니다"}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(t);
                }}>
                <Trash2 size={14} />
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
