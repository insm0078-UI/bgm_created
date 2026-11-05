import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export type Tone = "preset" | "mood" | "instrument" | "duration";

interface Props {
  tone: Tone;
  icon: LucideIcon;
  title: string;
  hint?: string;
  children: ReactNode;
}

/** Color-coded panel section; the tone sets the accent used by its header and chips. */
export function Section({ tone, icon: Icon, title, hint, children }: Props) {
  return (
    <section className={`sec tone-${tone}`}>
      <header className="sec-head">
        <span className="sec-icon"><Icon size={14} strokeWidth={2.2} /></span>
        <span className="sec-title">{title}</span>
        {hint && <span className="sec-hint">{hint}</span>}
      </header>
      {children}
    </section>
  );
}
