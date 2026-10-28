import { createHmac, randomBytes } from "node:crypto";
import { parseFiles, unzip } from "./artifact";
import { env } from "./config";
import { github, type WfRun } from "./github";
import type { RecentRow, Result, RunState } from "./types";

const B32 = "abcdefghijklmnopqrstuvwxyz234567";
export const ID = /^[0-9a-f]{6}[a-z2-7]{8}$/;
const WAITING = new Set(["queued", "pending", "waiting", "requested"]);

/** 6 hex of a salted HMAC of the IP: the per-IP limit counts this prefix in run-names, so no store is needed. */
export const ipTag = (ip: string) => createHmac("sha256", env.salt).update(ip).digest("hex").slice(0, 6);

export function newRequestId(ip: string) {
  const rand = Array.from(randomBytes(8), (b) => B32[b % 32]).join("");
  return ipTag(ip) + rand;
}

export const requestIdOf = (run: WfRun) => run.display_title.match(/^try-it ([0-9a-f]{6}[a-z2-7]{8})$/)?.[1] ?? null;

export const todayUtc = (now = new Date()) => now.toISOString().slice(0, 10);

export async function todaysRuns() {
  return (await github.runs(todayUtc())).filter(requestIdOf);
}

export type Limits = { used: number; cap: number; remaining: number };

export function limitsFrom(runs: WfRun[]): Limits {
  const used = runs.length;
  return { used, cap: env.dailyCap, remaining: Math.max(0, env.dailyCap - used) };
}

export type Refusal = { status: number; reason: string; message: string; waiting?: string; retry_minutes?: number };

/** Daily cap, one waiting run at a time, and the per-IP hourly limit. Null when a new run may start. */
export function refusal(runs: WfRun[], ip: string, now = Date.now()): Refusal | null {
  const { remaining } = limitsFrom(runs);
  if (remaining <= 0) {
    return { status: 429, reason: "daily_cap", message: `Today's ${env.dailyCap} free reviews are used up. They reset at 00:00 UTC.` };
  }
  // GitHub keeps one running and one pending run per concurrency group; a third dispatch cancels the pending one.
  const waiting = runs.find((r) => WAITING.has(r.status));
  if (waiting) {
    return { status: 409, reason: "one_waiting", message: "A review is already waiting for its turn. Try again in a minute, or watch it.", waiting: requestIdOf(waiting) ?? undefined };
  }
  const tag = ipTag(ip);
  const mine = runs.filter((r) => requestIdOf(r)?.startsWith(tag) && now - Date.parse(r.created_at) < 3600_000);
  if (mine.length >= env.ipHourly) {
    const oldest = Math.min(...mine.map((r) => Date.parse(r.created_at)));
    const retry = Math.max(1, Math.ceil((oldest + 3600_000 - now) / 60_000));
    return { status: 429, reason: "ip_hourly", message: `You've started ${env.ipHourly} reviews this hour. Try again in ${retry} minute${retry === 1 ? "" : "s"}.`, retry_minutes: retry };
  }
  return null;
}

// Finished artifacts never change: keep them for the life of the server instance.
const results = new Map<number, Result | null>();

export async function resultOf(runId: number): Promise<Result | null> {
  if (results.has(runId)) return results.get(runId)!;
  const zip = await github.artifact(runId);
  const result = zip ? parseFiles(unzip(zip)) : null;
  if (result) results.set(runId, result);
  return result;
}

async function locate(id: string, hint?: number) {
  if (hint) {
    const r = await github.run(hint);
    if (r && requestIdOf(r) === id) return r;
  }
  return (await github.runs()).find((r) => requestIdOf(r) === id) ?? null;
}

export async function runState(id: string, hint?: number): Promise<RunState> {
  const now = new Date().toISOString();
  const run = await locate(id, hint);
  if (!run) return { id, found: false, now, steps: [] };
  const status = WAITING.has(run.status) ? "queued" : run.status === "completed" ? "completed" : "in_progress";
  const state: RunState = {
    id, found: true, run_id: run.id, status, conclusion: run.conclusion, now,
    created_at: run.created_at, started_at: run.run_started_at, updated_at: run.updated_at, run_url: run.html_url,
    steps: status === "queued" ? [] : await github.steps(run.id),
  };
  if (status === "queued") {
    const recent = await github.runs(todayUtc(new Date(Date.parse(run.created_at) - 86_400_000)));
    state.ahead = recent.filter(
      (r) => r.id !== run.id && (r.status === "in_progress" || (WAITING.has(r.status) && r.created_at < run.created_at)),
    ).length;
  }
  if (status === "completed") state.result = await resultOf(run.id);
  return state;
}

export async function recent(limit = 10): Promise<RecentRow[]> {
  const runs = (await github.runs()).filter((r) => r.status === "completed" && requestIdOf(r)).slice(0, limit);
  return Promise.all(
    runs.map(async (r) => {
      const res = await resultOf(r.id).catch(() => null);
      return {
        id: requestIdOf(r)!,
        created_at: r.created_at,
        pr_url: res?.meta?.pr_url ?? null,
        repo: res?.meta?.repo ?? null,
        number: res?.meta?.number ?? null,
        title: res?.meta?.title ?? null,
        verdict: res?.review?.verdict ?? (r.conclusion === "success" ? null : "error"),
        cost_usd: res?.review?.cost_usd ?? null,
        seconds: res?.review?.seconds ?? null,
      };
    }),
  );
}

export function clientIp(headers: Headers) {
  return headers.get("x-forwarded-for")?.split(",")[0].trim() || headers.get("x-real-ip") || "local";
}
