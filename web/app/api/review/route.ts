import { NextResponse } from "next/server";
import { allowed } from "@/lib/config";
import { github } from "@/lib/github";
import { parseTarget, prUrl } from "@/lib/parse-url";
import { clientIp, newRequestId, refusal, todaysRuns } from "@/lib/service";

const fail = (status: number, reason: string, message: string, extra: object = {}) =>
  NextResponse.json({ error: { reason, message, ...extra } }, { status });

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const target = parseTarget(String(body?.url ?? ""));
  if (!target) return fail(400, "bad_url", "That isn't a GitHub repo or pull request URL.");
  if (!allowed(target.repo)) {
    return fail(403, "not_allowlisted", `Try it only runs on the demo repo for now. ${target.repo} can run Red2Fix in its own GitHub Actions.`);
  }
  try {
    if (target.kind === "repo") {
      const prs = await github.openPrs(target.repo);
      return NextResponse.json({ kind: "repo", repo: target.repo, prs });
    }
    const pr = await github.pr(target.repo, target.number);
    if (!pr) return fail(404, "no_pr", `${target.repo} has no pull request #${target.number}.`);
    const ip = clientIp(req.headers);
    const no = refusal(await todaysRuns(), ip);
    if (no) return fail(no.status, no.reason, no.message, { waiting: no.waiting, retry_minutes: no.retry_minutes });
    const id = newRequestId(ip);
    await github.dispatch(prUrl(target.repo, target.number), id);
    return NextResponse.json({ kind: "run", id });
  } catch (e) {
    console.error(e);
    return fail(502, "github", "GitHub didn't answer. Try again in a moment.");
  }
}
