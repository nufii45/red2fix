const int = (v: string | undefined, d: number) => (v && /^\d+$/.test(v) ? Number(v) : d);

export const env = {
  token: process.env.GITHUB_DISPATCH_TOKEN ?? "",
  // The repo that hosts .github/workflows/try-it.yml.
  agentRepo: process.env.TRYIT_AGENT_REPO ?? "nufii45/red2fix",
  workflow: process.env.TRYIT_WORKFLOW ?? "try-it.yml",
  ref: process.env.TRYIT_REF ?? "main",
  repos: (process.env.TRYIT_REPOS ?? "nufii45/red2fix-minikit")
    .split(",")
    .map((r) => r.trim().toLowerCase())
    .filter(Boolean),
  dailyCap: int(process.env.TRYIT_DAILY_CAP, 25),
  ipHourly: int(process.env.TRYIT_IP_HOURLY, 3),
  salt: process.env.TRYIT_SALT ?? "local-dev-salt",
};

/** Without a token, GitHub is simulated from the recorded runs in fixtures/. */
export const fake = process.env.TRYIT_FAKE_GITHUB === "1" || !env.token;

export const allowed = (repo: string) => env.repos.includes(repo.toLowerCase());
