import { describe, expect, it } from "vitest";
import type { WfRun } from "./github";
import { DEFAULT_REPOS, ipTag, isAllowed, limitsFrom, parseRepos, refusal, requestIdOf } from "./limits";

const RULES = { cap: 3, ipHourly: 2, salt: "s" };
const NOW = Date.parse("2026-10-29T12:00:00Z");
const me = ipTag("1.2.3.4", RULES.salt);
const other = ipTag("5.6.7.8", RULES.salt);

let n = 0;
const run = (tag: string, status = "completed", minutesAgo = 90): WfRun => ({
  id: ++n, display_title: `try-it ${tag}${"abcdefgh"}`, status, conclusion: null, html_url: "",
  created_at: new Date(NOW - minutesAgo * 60_000).toISOString(), run_started_at: null, updated_at: "",
});

describe("allowlist", () => {
  it("defaults to the demo repo when unset or blank", () => {
    expect(parseRepos(undefined)).toEqual([DEFAULT_REPOS]);
    expect(parseRepos(" , ")).toEqual([DEFAULT_REPOS]);
  });
  it("is one comma-separated env value, case-insensitive", () => {
    const repos = parseRepos("nufii45/red2fix-minikit, Psf/Requests");
    expect(isAllowed("psf/requests", repos)).toBe(true);
    expect(isAllowed("NUFII45/red2fix-minikit", repos)).toBe(true);
    expect(isAllowed("psf/requests-extra", repos)).toBe(false);
  });
  it("an explicit list replaces the default", () => {
    expect(isAllowed(DEFAULT_REPOS, parseRepos("psf/requests"))).toBe(false);
  });
});

describe("daily cap", () => {
  it("counts only try-it runs", () => {
    const runs = [run(me), { ...run(me), display_title: "red2fix" }, { ...run(me), display_title: "try-it nope" }];
    expect(limitsFrom(runs, 3)).toEqual({ used: 1, cap: 3, remaining: 2 });
  });
  it("refuses at the cap and never goes negative", () => {
    const runs = [run(other), run(other), run(other), run(other)];
    expect(limitsFrom(runs, 3).remaining).toBe(0);
    expect(refusal(runs, "1.2.3.4", RULES, NOW)?.reason).toBe("daily_cap");
  });
  it("allows the run under the cap", () => {
    expect(refusal([run(other), run(other)], "1.2.3.4", RULES, NOW)).toBeNull();
  });
});

describe("queue and per-IP", () => {
  it("refuses while a run is waiting, and names it", () => {
    const waiting = run(other, "queued", 1);
    const r = refusal([run(other, "in_progress", 2), waiting], "1.2.3.4", { ...RULES, cap: 25 }, NOW);
    expect(r).toMatchObject({ status: 409, reason: "one_waiting", waiting: requestIdOf(waiting) });
  });
  it("one running run doesn't block a second", () => {
    expect(refusal([run(other, "in_progress", 2)], "1.2.3.4", { ...RULES, cap: 25 }, NOW)).toBeNull();
  });
  it("limits one IP per hour, with the time to wait", () => {
    const runs = [run(me, "completed", 50), run(me, "completed", 10), run(other, "completed", 5)];
    expect(refusal(runs, "1.2.3.4", { ...RULES, cap: 25 }, NOW)).toMatchObject({ reason: "ip_hourly", retry_minutes: 10 });
    expect(refusal(runs, "5.6.7.8", { ...RULES, cap: 25 }, NOW)).toBeNull();
  });
  it("runs older than an hour don't count", () => {
    expect(refusal([run(me, "completed", 61), run(me, "completed", 70)], "1.2.3.4", { ...RULES, cap: 25 }, NOW)).toBeNull();
  });
  it("the tag is salted and 6 hex", () => {
    expect(me).toMatch(/^[0-9a-f]{6}$/);
    expect(ipTag("1.2.3.4", "other-salt")).not.toBe(me);
  });
});
