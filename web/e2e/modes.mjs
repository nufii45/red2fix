// Checks the server-rendered pages for the site's mode: the replay banner on run views, and on production without
// a token the "Live reviews are offline" notice with only the examples left.
// Usage: node e2e/modes.mjs <base-url> <live|replay|offline>   (server running in that mode)
const [base = "http://localhost:3300", mode = "replay"] = process.argv.slice(2);
const html = async (path) => (await fetch(base + path)).text();

const home = await html("/");
const run = await html("/r/5e1a07k2m4p6q7");
const checks = {
  "replay banner on run views only when replaying": run.includes("Replay of a recorded review, not a live run.") === (mode !== "live"),
  "offline notice only when offline": home.includes("Live reviews are offline.") === (mode === "offline"),
  "URL field unless offline": home.includes('aria-label="GitHub repo or pull request URL"') === (mode !== "offline"),
  "home keeps the examples": home.includes("Review example good, pull request 4"),
};
let bad = 0;
for (const [name, ok] of Object.entries(checks)) {
  if (!ok) bad++;
  console.log(`${ok ? "ok  " : "FAIL"} ${mode}: ${name}`);
}
process.exit(bad ? 1 : 0);
