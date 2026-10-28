/**
 * GitHub simulated in memory for local runs and the smoke test: dispatched runs queue one at a time and
 * replay the recorded demo reviews in fixtures/ (real review.json, ledger and events from out/review-*).
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { strToU8, zipSync } from "fflate";
import { DEMO_REPO, EXAMPLES } from "./examples";
import type { GitHub, Pr, WfRun } from "./github";
import type { Step } from "./types";

type FakeRun = { id: number; requestId: string; prUrl: string; created: number };

const SETUP = ["Set up job", "Check out the reviewer", "Fetch the PR", "Check out the repo at base", "Set up Python", "Install the repo"];
const AFTER = ["Upload the evidence", "Complete job"];
const PICKUP_MS = 3000;

const store = globalThis as unknown as { __tryit?: { runs: FakeRun[]; next: number } };

function fixtureFor(prUrl: string) {
  const n = Number(prUrl.split("/").pop());
  return EXAMPLES.find((e) => e.number === n)?.name ?? "good";
}

function read(name: string, file: string) {
  try {
    return readFileSync(path.join(process.cwd(), "fixtures", name, file), "utf8");
  } catch {
    return "";
  }
}

const reviewSeconds = (name: string) => {
  try {
    return Math.round(JSON.parse(read(name, "review.json")).seconds) || 30;
  } catch {
    return 30;
  }
};

function state() {
  if (!store.__tryit) {
    const now = Date.now();
    const dayStart = new Date(new Date(now).toISOString().slice(0, 10)).getTime();
    // A few finished runs from earlier today, so "recent" and the daily count look like a real day.
    const seeds = ["breaks", "good", "inject2", "wrong"].map((name, i) => ({
      id: 9000 + i,
      requestId: `${["5e1a07", "a2c4f9", "0b7d3e", "c81f22"][i]}${["k2m4p6q7", "t3v5x7z2", "b4d6f2h3", "j5l7n3r4"][i]}`,
      prUrl: `https://github.com/${DEMO_REPO}/pull/${EXAMPLES.find((e) => e.name === name)!.number}`,
      created: Math.max(dayStart + 60_000 * (i + 1), now - (4 - i) * 47 * 60_000),
    }));
    store.__tryit = { runs: seeds, next: 9100 };
  }
  return store.__tryit;
}

/** Start, end and step timings, scheduled one at a time in creation order (the "try-it" concurrency group). */
function schedule() {
  let free = 0;
  return state()
    .runs.slice()
    .sort((a, b) => a.created - b.created)
    .map((r) => {
      const start = Math.max(r.created + PICKUP_MS, free);
      const review = reviewSeconds(fixtureFor(r.prUrl)) * 1000;
      const end = start + SETUP.length * 1000 + review + AFTER.length * 1000;
      free = end;
      return { r, start, end, review };
    });
}

const iso = (ms: number) => new Date(ms).toISOString();

function toRun({ r, start, end }: ReturnType<typeof schedule>[number], now: number): WfRun {
  const status = now < start ? "queued" : now < end ? "in_progress" : "completed";
  return {
    id: r.id,
    display_title: `try-it ${r.requestId}`,
    status,
    conclusion: status === "completed" ? "success" : null,
    created_at: iso(r.created),
    run_started_at: now >= start ? iso(start) : null,
    updated_at: iso(Math.min(now, end)),
    html_url: "https://github.com/nufii45/red2fix/actions",
  };
}

const find = (runId: number) => schedule().find((s) => s.r.id === runId);

const pr = (n: number): Pr | null => {
  const e = EXAMPLES.find((x) => x.number === n);
  return e
    ? { number: n, title: e.title, state: "open", user: "nufii45", updated_at: "2026-10-28T08:00:00Z", html_url: `https://github.com/${DEMO_REPO}/pull/${n}` }
    : null;
};

export const fakeGitHub: GitHub = {
  async runs(since) {
    const now = Date.now();
    const from = since ? Date.parse(since) : 0;
    return schedule()
      .filter((s) => s.r.created >= from && s.r.created <= now)
      .map((s) => toRun(s, now))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  },
  async run(runId) {
    const s = find(runId);
    return s ? toRun(s, Date.now()) : null;
  },
  async dispatch(prUrl, requestId) {
    const st = state();
    st.runs.push({ id: st.next++, requestId, prUrl, created: Date.now() });
  },
  async steps(runId) {
    const s = find(runId);
    const now = Date.now();
    if (!s || now < s.start) return [];
    const durations = [...SETUP.map(() => 1000), s.review, ...AFTER.map(() => 1000)];
    const names = [...SETUP, "Review", ...AFTER];
    let t = s.start;
    return names.map((name, i): Step => {
      const a = t;
      const b = (t += durations[i]);
      const status = now >= b ? "completed" : now >= a ? "in_progress" : "queued";
      return {
        name,
        status,
        conclusion: status === "completed" ? "success" : null,
        started_at: now >= a ? iso(a) : null,
        completed_at: now >= b ? iso(b) : null,
      };
    });
  },
  async artifact(runId) {
    const s = find(runId);
    if (!s || Date.now() < s.end) return null;
    const name = fixtureFor(s.r.prUrl);
    const n = Number(s.r.prUrl.split("/").pop());
    const meta = {
      request_id: s.r.requestId, pr_url: s.r.prUrl, repo: DEMO_REPO, number: n,
      title: pr(n)?.title ?? "", spec_source: "issue",
    };
    const files: Record<string, Uint8Array> = { "out/meta.json": strToU8(JSON.stringify(meta)) };
    for (const f of ["review.json", "review.md", "ledger.jsonl", "events.jsonl", "repro_test.py"]) {
      const text = read(name, f);
      if (text) files[`out/${f}`] = strToU8(text);
    }
    return zipSync(files);
  },
  async pr(repo, n) {
    return repo.toLowerCase() === DEMO_REPO ? pr(n) : null;
  },
  async openPrs(repo) {
    if (repo.toLowerCase() !== DEMO_REPO) return [];
    return EXAMPLES.flatMap((e) => (e.number ? [pr(e.number)!] : []));
  },
};
