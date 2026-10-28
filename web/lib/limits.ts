import { createHmac } from "node:crypto";
import type { WfRun } from "./github";

/** Pure limit rules, shared by the API routes and the unit tests. Mirrors scripts/tryit_fetch.py. */

export const DEFAULT_REPOS = "nufii45/red2fix-minikit";
export const ID = /^[0-9a-f]{6}[a-z2-7]{8}$/;
const RUN_NAME = /^try-it ([0-9a-f]{6}[a-z2-7]{8})$/;
export const WAITING = new Set(["queued", "pending", "waiting", "requested"]);

export function parseRepos(value: string | undefined) {
  const repos = (value ?? "").split(",").map((r) => r.trim().toLowerCase()).filter(Boolean);
  return repos.length ? repos : [DEFAULT_REPOS];
}

export const isAllowed = (repo: string, repos: string[]) => repos.includes(repo.toLowerCase());

export const ipTag = (ip: string, salt: string) => createHmac("sha256", salt).update(ip).digest("hex").slice(0, 6);

export const requestIdOf = (run: Pick<WfRun, "display_title">) => run.display_title.match(RUN_NAME)?.[1] ?? null;

export type Limits = { used: number; cap: number; remaining: number };

/** Today's try-it runs (already filtered to today, UTC) against the daily cap. */
export function limitsFrom(runs: WfRun[], cap: number): Limits {
  const used = runs.filter((r) => requestIdOf(r)).length;
  return { used, cap, remaining: Math.max(0, cap - used) };
}

export type Refusal = { status: number; reason: string; message: string; waiting?: string; retry_minutes?: number };
export type Rules = { cap: number; ipHourly: number; salt: string };

/** Daily cap, then one waiting run at a time, then the per-IP hourly limit. Null when a run may start. */
export function refusal(runs: WfRun[], ip: string, rules: Rules, now = Date.now()): Refusal | null {
  const mine = runs.filter((r) => requestIdOf(r));
  if (limitsFrom(mine, rules.cap).remaining <= 0) {
    return { status: 429, reason: "daily_cap", message: `Today's ${rules.cap} free reviews are used up. They reset at 00:00 UTC.` };
  }
  // GitHub keeps one running and one pending run per concurrency group; a third dispatch cancels the pending one.
  const waiting = mine.find((r) => WAITING.has(r.status));
  if (waiting) {
    return {
      status: 409, reason: "one_waiting", waiting: requestIdOf(waiting) ?? undefined,
      message: "A review is already waiting for its turn. Try again in a minute, or watch it.",
    };
  }
  const tag = ipTag(ip, rules.salt);
  const recent = mine.filter((r) => requestIdOf(r)!.startsWith(tag) && now - Date.parse(r.created_at) < 3600_000);
  if (recent.length >= rules.ipHourly) {
    const oldest = Math.min(...recent.map((r) => Date.parse(r.created_at)));
    const retry = Math.max(1, Math.ceil((oldest + 3600_000 - now) / 60_000));
    return {
      status: 429, reason: "ip_hourly", retry_minutes: retry,
      message: `You've started ${rules.ipHourly} reviews this hour. Try again in ${retry} minute${retry === 1 ? "" : "s"}.`,
    };
  }
  return null;
}
