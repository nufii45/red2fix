import { isAllowed, parseRepos } from "./limits";

const int = (v: string | undefined, d: number) => (v && /^\d+$/.test(v) ? Number(v) : d);

export const env = {
  token: process.env.GITHUB_DISPATCH_TOKEN ?? "",
  // The repo that hosts .github/workflows/try-it.yml.
  agentRepo: process.env.TRYIT_AGENT_REPO ?? "nufii45/red2fix",
  workflow: process.env.TRYIT_WORKFLOW ?? "try-it.yml",
  ref: process.env.TRYIT_REF ?? "main",
  // Keep in step with the workflow's TRYIT_REPOS repo variable, which checks again inside the run.
  repos: parseRepos(process.env.TRYIT_REPOS),
  dailyCap: int(process.env.TRYIT_DAILY_CAP, 25),
  ipHourly: int(process.env.TRYIT_IP_HOURLY, 3),
  salt: process.env.TRYIT_SALT ?? "local-dev-salt",
};

/**
 * replay: GitHub is simulated from the recorded runs in fixtures/ (no token, or TRYIT_FAKE_GITHUB=1 outside production).
 * offline: Vercel production without a token never replays quietly; it says live reviews are offline and replays
 * only the examples.
 */
export function modeOf(e: Record<string, string | undefined>) {
  const token = !!e.GITHUB_DISPATCH_TOKEN;
  const production = e.VERCEL_ENV === "production";
  return { replay: !token || (!production && e.TRYIT_FAKE_GITHUB === "1"), offline: production && !token };
}

export const { replay: fake, offline } = modeOf(process.env);

export const allowed = (repo: string) => isAllowed(repo, env.repos);
