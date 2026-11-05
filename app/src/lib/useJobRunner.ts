// Starts an engine job, polls it until it finishes, and supports cancelling.

import { useRef, useState } from "react";
import { cancelJob, getJob, type Job, type TrackResult } from "./engine";

export type JobOutcome =
  | { kind: "done"; results: TrackResult[] }
  | { kind: "failed"; error: string }
  | { kind: "cancelled" };

export function useJobRunner() {
  const [job, setJob] = useState<Job | null>(null);
  const current = useRef<string | null>(null);
  const busy = job !== null && (job.status === "queued" || job.status === "running");

  async function run(start: () => Promise<Job>): Promise<JobOutcome> {
    try {
      let j = await start();
      current.current = j.id;
      setJob(j);
      while (j.status === "queued" || j.status === "running") {
        await new Promise((r) => setTimeout(r, 400));
        j = await getJob(j.id);
        setJob(j);
      }
      if (j.status === "done") return { kind: "done", results: j.results };
      if (j.status === "cancelled") return { kind: "cancelled" };
      return { kind: "failed", error: j.error ?? "음악 생성에 실패했습니다." };
    } catch (e) {
      setJob(null);
      return { kind: "failed", error: e instanceof Error ? e.message : String(e) };
    } finally {
      current.current = null;
    }
  }

  async function cancel() {
    if (current.current) setJob(await cancelJob(current.current));
  }

  return { job, busy, run, cancel };
}
