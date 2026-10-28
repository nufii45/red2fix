import type { Phase, RunState } from "./types";

/** Workflow step names in .github/workflows/try-it.yml. Renaming a step there means renaming it here. */
export const REVIEW_STEP = "Review";
export const INSTALL_STEP = "Install the repo";

export const BAR = ["Queued", "Setting up", "Writing test", "Red on base", "Green on PR", "Review", "Verdict"] as const;

/** Agent phases (events.jsonl) per bar step, for the real timings once a run is done. */
const PHASES: Record<number, string[]> = {
  2: ["TRIAGE", "BASELINE", "LOCALIZE", "REPRODUCE"],
  3: ["VERIFY_RED", "COMMIT_REPRO"],
  4: ["APPLY_PR", "HEAD_CHECK"],
  5: ["REVIEW"],
  6: ["VERDICT", "FIX", "CHECK", "ESCALATE", "CONFIRM", "SUMMARIZE", "DONE"],
};

/** While the Review step runs, the job API can't see inside it: share of a typical demo review per phase. */
const EXPECTED_S = 35;
const SPLIT = [0.6, 0.75, 0.8]; // ends of Writing test, Red on base, Green on PR

export type Bar = {
  current: number; // index into BAR; BAR.length when everything is done
  failedAt: number | null;
  estimated: boolean;
  seconds: (number | null)[]; // real per-step durations, finished runs only
};

const secs = (a?: string | null, b?: string | null) => (a && b ? (Date.parse(b) - Date.parse(a)) / 1000 : null);

export function phaseSeconds(phases: Phase[]): (number | null)[] {
  const out: (number | null)[] = BAR.map(() => null);
  phases.forEach((p, i) => {
    const next = phases[i + 1];
    const idx = Number(Object.keys(PHASES).find((k) => PHASES[Number(k)].includes(p.name)));
    if (!Number.isNaN(idx) && next) out[idx] = (out[idx] ?? 0) + (next.t - p.t);
  });
  return out;
}

export function bar(run: RunState, nowMs: number): Bar {
  const none = { failedAt: null, estimated: false, seconds: BAR.map(() => null) };
  if (!run.found || !run.status || run.status === "queued") return { ...none, current: 0 };
  const review = run.steps.find((s) => s.name === REVIEW_STEP);
  if (run.status === "completed") {
    const phases = run.result?.phases ?? [];
    const seconds = phaseSeconds(phases);
    const setup = run.steps.filter((s) => s.name !== REVIEW_STEP && s.started_at);
    seconds[1] = secs(setup[0]?.started_at, (review?.started_at ?? setup.at(-1)?.completed_at) || null);
    const verdict = run.result?.review?.verdict;
    if (verdict && verdict !== "error") return { ...none, current: BAR.length, seconds };
    // Error: stop the bar at the last step the run reached.
    const reached = phases.length
      ? Math.max(...phases.map((p) => Number(Object.keys(PHASES).find((k) => PHASES[Number(k)].includes(p.name)) ?? 1)))
      : 1;
    return { ...none, current: reached, failedAt: reached, seconds };
  }
  if (!review?.started_at || review.status !== "in_progress") return { ...none, current: 1 };
  const f = (nowMs - Date.parse(review.started_at)) / 1000 / EXPECTED_S;
  const current = f < SPLIT[0] ? 2 : f < SPLIT[1] ? 3 : f < SPLIT[2] ? 4 : 5; // never past Review until it ends
  return { ...none, current, estimated: true };
}

export function elapsed(run: RunState, nowMs: number) {
  if (!run.created_at) return 0;
  const end = run.status === "completed" && run.updated_at ? Date.parse(run.updated_at) : nowMs;
  return Math.max(0, (end - Date.parse(run.created_at)) / 1000);
}

export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
