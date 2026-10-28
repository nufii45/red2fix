// Screenshots at phone and desktop width, plus a horizontal-overflow check.
// Usage: node e2e/screens.mjs [base-url] [out-dir]   (dev server running; uses the installed Chrome)
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:3300";
const out = process.argv[3] ?? "../docs/screenshots";
const sizes = { phone: { width: 390, height: 844 }, desktop: { width: 1440, height: 900 } };

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext();
const page = await ctx.newPage();

// Review two examples one after the other and wait for each verdict, for the run view shots.
async function review(name) {
  await page.goto(base);
  await page.getByRole("button", { name: new RegExp(`example ${name},`, "i") }).click();
  await page.waitForURL(/\/r\//);
  const url = new URL(page.url());
  await page.getByLabel("Verdict").waitFor({ timeout: 150_000 });
  return url.pathname + url.search;
}
const run = await review("good");
const runAdvisory = await review("dep-advisory");

const pages = { home: "/", run, "run-advisory": runAdvisory, results: "/results", install: "/install", recent: "/recent" };
let bad = 0;
for (const [size, vp] of Object.entries(sizes)) {
  for (const [name, path] of Object.entries(pages)) {
    for (const scheme of ["light", "dark"]) {
      const c = await browser.newContext({ viewport: vp, colorScheme: scheme, deviceScaleFactor: 2 });
      const p = await c.newPage();
      await p.goto(base + path, { waitUntil: "networkidle" });
      if (name === "run") await p.getByLabel("Verdict").waitFor();
      await p.waitForTimeout(400);
      const w = await p.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      if (w[0] > w[1]) {
        bad++;
        console.log(`OVERFLOW ${name} ${size} ${scheme}: ${w[0]} > ${w[1]}`);
      }
      if (scheme === "light") await p.screenshot({ path: `${out}/web-${name}-${size}.png`, fullPage: true });
      await c.close();
    }
  }
}
await browser.close();
console.log(bad ? `${bad} overflow(s)` : "no horizontal overflow");
process.exit(bad ? 1 : 0);
