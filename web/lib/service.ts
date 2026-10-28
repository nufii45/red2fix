import { randomBytes } from "node:crypto";
import { parseFiles, unzip } from "./artifact";
import { env } from "./config";
import { github, type WfRun } from "./github";
import { ID, ipTag, limitsFrom as limitsFor, refusal as refusalFor, requestIdOf, WAITING } from "./limits";
import type { RecentRow, Result, RunState } from "./types";

export { ID, requestIdOf };

const B32 = "abcdefghijklmnopqrstuvwxyz234567";
const rules = () => ({ cap: env.dailyCap, ipHourly: env.ipHourly, salt: env.salt });

/** 6 hex of a salted HMAC of the IP, then 8 random: the per-IP limit counts the prefix in run-names. */
export function newRequestId(ip: string) {
  const rand = Array.from(randomBytes(8), (b) => B32[b % 32]).join("");
  return ipTag(ip, env.salt) + rand;
}

export const todayUtc = (now = new Date()) => now.toISOString().slice(0, 10);

export async function todaysRuns() {
  return (await github.runs(todayUtc())).filter(requestIdOf);
}

export const limitsFrom = (runs: WfRun[]) => limitsFor(runs, env.dailyCap);
export const refusal = (runs: WfRun[], ip: string) => refusalFor(runs, ip, rules());

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
