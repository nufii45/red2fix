import { NextResponse } from "next/server";
import { ID, runState } from "@/lib/service";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!ID.test(id)) return NextResponse.json({ error: { reason: "bad_id", message: "That isn't a review id." } }, { status: 400 });
  const hint = Number(new URL(req.url).searchParams.get("run")) || undefined;
  try {
    const state = await runState(id, hint);
    const done = state.status === "completed" && state.result;
    return NextResponse.json(state, {
      headers: { "Cache-Control": done ? "public, s-maxage=31536000, immutable" : "public, s-maxage=3" },
    });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: { reason: "github", message: "GitHub didn't answer." } }, { status: 502 });
  }
}
