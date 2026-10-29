import { afterEach, describe, expect, it, vi } from "vitest";
import { modeOf } from "./config";

describe("modeOf", () => {
  it("replays locally without a token, or when asked to", () => {
    expect(modeOf({})).toEqual({ replay: true, offline: false });
    expect(modeOf({ GITHUB_DISPATCH_TOKEN: "t", TRYIT_FAKE_GITHUB: "1" })).toEqual({ replay: true, offline: false });
    expect(modeOf({ VERCEL_ENV: "preview" })).toEqual({ replay: true, offline: false });
  });

  it("is never a quiet replay on Vercel production", () => {
    expect(modeOf({ VERCEL_ENV: "production" })).toEqual({ replay: true, offline: true });
    expect(modeOf({ VERCEL_ENV: "production", GITHUB_DISPATCH_TOKEN: "t", TRYIT_FAKE_GITHUB: "1" }))
      .toEqual({ replay: false, offline: false });
  });
});

describe("POST /api/review on production without a token", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  async function post(url: string) {
    vi.stubEnv("VERCEL_ENV", "production");
    vi.stubEnv("GITHUB_DISPATCH_TOKEN", "");
    vi.resetModules();
    const { POST } = await import("@/app/api/review/route");
    const res = await POST(new Request("http://x/api/review", { method: "POST", body: JSON.stringify({ url }) }));
    return { status: res.status, body: await res.json() };
  }

  it("refuses anything but the examples", async () => {
    for (const url of ["https://github.com/nufii45/red2fix-minikit/pull/99", "https://github.com/nufii45/red2fix-minikit"]) {
      const { status, body } = await post(url);
      expect(status).toBe(503);
      expect(body.error.reason).toBe("offline");
      expect(body.error.message).toMatch(/^Live reviews are offline/);
    }
  });

  it("still replays an example", async () => {
    const { status, body } = await post("https://github.com/nufii45/red2fix-minikit/pull/4");
    expect(status).toBe(200);
    expect(body.kind).toBe("run");
  });
});
