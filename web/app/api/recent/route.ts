import { NextResponse } from "next/server";
import { recent } from "@/lib/service";

export async function GET() {
  try {
    return NextResponse.json({ runs: await recent(10) }, { headers: { "Cache-Control": "public, s-maxage=30" } });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: { reason: "github", message: "Couldn't load recent reviews." } }, { status: 502 });
  }
}
