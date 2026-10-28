export type Target = { kind: "repo"; repo: string } | { kind: "pr"; repo: string; number: number };

const NAME = /^[A-Za-z0-9_.-]+$/;

/** github.com/owner/name or github.com/owner/name/pull/N, with or without scheme, .git or trailing paths. */
export function parseTarget(input: string): Target | null {
  let s = input.trim();
  if (!s) return null;
  if (!/^https?:\/\//i.test(s)) s = `https://${s}`;
  let url: URL;
  try {
    url = new URL(s);
  } catch {
    return null;
  }
  if (!/^(www\.)?github\.com$/i.test(url.hostname)) return null;
  const [owner, rawName, kind, num] = url.pathname.split("/").filter(Boolean);
  const name = rawName?.replace(/\.git$/i, "");
  if (!owner || !name || !NAME.test(owner) || !NAME.test(name)) return null;
  const repo = `${owner}/${name}`;
  if (kind === "pull" || kind === "pulls") {
    return num && /^\d+$/.test(num) ? { kind: "pr", repo, number: Number(num) } : null;
  }
  return { kind: "repo", repo };
}

export const prUrl = (repo: string, n: number) => `https://github.com/${repo}/pull/${n}`;
