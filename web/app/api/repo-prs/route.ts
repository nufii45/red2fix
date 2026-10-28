import { NextResponse } from "next/server";
import { allowed } from "@/lib/config";
import { github } from "@/lib/github";

export async function GET(req: Request) {
  const repo = new URL(req.url).searchParams.get("repo") ?? "";
  if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) {
    return NextResponse.json({ error: { reason: "bad_repo", message: "Use owner/name." } }, { status: 400 });
  }
  if (!allowed(repo)) {
    return NextResponse.json({ error: { reason: "not_allowlisted", message: "Try it only runs on the demo repo for now." } }, { status: 403 });
  }
  try {
    return NextResponse.json({ repo, prs: await github.openPrs(repo) }, { headers: { "Cache-Control": "public, s-maxage=30" } });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: { reason: "github", message: "GitHub didn't answer." } }, { status: 502 });
  }
}
