import { NextResponse } from "next/server";
import { fake } from "@/lib/config";
import { limitsFrom, todaysRuns } from "@/lib/service";

export async function GET() {
  try {
    return NextResponse.json({ ...limitsFrom(await todaysRuns()), simulated: fake }, { headers: { "Cache-Control": "public, s-maxage=15" } });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: { reason: "github", message: "Couldn't count today's runs." } }, { status: 502 });
  }
}
