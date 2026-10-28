import { env, fake } from "./config";
import { fakeGitHub } from "./fake";
import type { Step } from "./types";

export type WfRun = {
  id: number;
  display_title: string;
  status: string; // queued | in_progress | completed | waiting | pending | requested
  conclusion: string | null;
  created_at: string;
  run_started_at: string | null;
  updated_at: string;
  html_url: string;
};

export type Pr = { number: number; title: string; state: string; user: string; updated_at: string; html_url: string };

export interface GitHub {
  /** try-it runs, newest first; only those created at or after `since` when given. */
  runs(since?: string): Promise<WfRun[]>;
  run(runId: number): Promise<WfRun | null>;
  dispatch(prUrl: string, requestId: string): Promise<void>;
  steps(runId: number): Promise<Step[]>;
  /** The run's artifact zip, or null if it has none (yet). */
  artifact(runId: number): Promise<Uint8Array | null>;
  pr(repo: string, n: number): Promise<Pr | null>;
  openPrs(repo: string): Promise<Pr[]>;
}

export class GitHubError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`https://api.github.com/${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...init.headers,
    },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new GitHubError(res.status, `GitHub ${res.status} on ${path}`);
  return res.status === 204 ? {} : res.json();
}

const toPr = (p: { number: number; title: string; state: string; user?: { login: string }; updated_at: string; html_url: string }): Pr => ({
  number: p.number, title: p.title, state: p.state, user: p.user?.login ?? "", updated_at: p.updated_at, html_url: p.html_url,
});

const wf = () => `repos/${env.agentRepo}/actions/workflows/${env.workflow}`;

const realGitHub: GitHub = {
  async runs(since) {
    const out: WfRun[] = [];
    for (let page = 1; page <= 3; page++) {
      const q = new URLSearchParams({ event: "workflow_dispatch", per_page: "100", page: String(page) });
      if (since) q.set("created", `>=${since}`);
      const data = await api(`${wf()}/runs?${q}`);
      const runs: WfRun[] = data?.workflow_runs ?? [];
      out.push(...runs);
      if (runs.length < 100) break;
    }
    return out;
  },
  async run(runId) {
    return api(`repos/${env.agentRepo}/actions/runs/${runId}`);
  },
  async dispatch(prUrl, requestId) {
    await api(`${wf()}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: env.ref, inputs: { pr_url: prUrl, request_id: requestId } }),
    });
  },
  async steps(runId) {
    const data = await api(`repos/${env.agentRepo}/actions/runs/${runId}/jobs`);
    return (data?.jobs?.[0]?.steps ?? []).map((s: Step) => ({
      name: s.name, status: s.status, conclusion: s.conclusion, started_at: s.started_at, completed_at: s.completed_at,
    }));
  },
  async artifact(runId) {
    const data = await api(`repos/${env.agentRepo}/actions/runs/${runId}/artifacts`);
    const a = data?.artifacts?.find((x: { name: string; expired: boolean }) => x.name.startsWith("try-it-") && !x.expired);
    if (!a) return null;
    // Redirects to blob storage; fetch drops the Authorization header on the cross-origin hop.
    const res = await fetch(a.archive_download_url, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${env.token}`, Accept: "application/vnd.github+json" },
    });
    if (!res.ok) throw new GitHubError(res.status, `artifact download ${res.status}`);
    return new Uint8Array(await res.arrayBuffer());
  },
  async pr(repo, n) {
    const p = await api(`repos/${repo}/pulls/${n}`);
    return p ? toPr(p) : null;
  },
  async openPrs(repo) {
    const ps = (await api(`repos/${repo}/pulls?state=open&per_page=50&sort=updated&direction=desc`)) ?? [];
    return ps.map(toPr);
  },
};

export const github: GitHub = fake ? fakeGitHub : realGitHub;
