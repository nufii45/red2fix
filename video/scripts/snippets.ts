// Extracts decide() from agent/review.py into src/data/snippets.json. Never retype code into a component.
// Usage: node scripts/snippets.ts [path to review.py]. Exits 1 if any marker is missing.
import fs from "node:fs";
import path from "node:path";

const here = path.dirname(new URL(import.meta.url).pathname);
const src = process.argv[2] ?? path.join(here, "../../agent/review.py");
const out = path.join(here, "../src/data/snippets.json");

const fail = (msg: string): never => {
  console.error(`snippets: ${msg} in ${src}. agent/review.py changed shape: update the markers.`);
  process.exit(1);
};
const find = (lines: string[], marker: string, from = 0) => {
  const i = lines.findIndex((l, n) => n >= from && l.includes(marker));
  return i < 0 ? fail(`marker not found: ${JSON.stringify(marker)}`) : i;
};

const all = fs.readFileSync(src, "utf8").split("\n");
const start = find(all, "def decide(");
const end = all.findIndex((l, n) => n > find(all, 'return "proven"', start) && l.trim() === "");
if (end < 0) fail('no blank line after return "proven"');
const lines = all.slice(start, end);

// Precedence steps, in the order decide() checks them; from/to index into lines.
const STEPS: [string, string, string][] = [
  ["error", 'if proof == "error"', 'return "error"'],
  ["breaks_tests", "if new_failures:", 'return "breaks_tests"'],
  ["doesnt_fix", 'if proof == "doesnt_fix":', 'return "doesnt_fix"'],
  ["unproven (needs_review if a blocker)", "blockers = [", 'return ("needs_review"'],
  ["needs_review", "if blockers or restricted_touched:", 'return "needs_review"'],
  ["needs_review", 'if spec_source == "pr_description":', 'return "needs_review"'],
  ["proven", 'return "proven"', 'return "proven"'],
];
const steps = STEPS.map(([label, a, b]) => {
  const from = find(lines, a);
  return { label, from, to: find(lines, b, from) };
});

fs.writeFileSync(out, JSON.stringify({ file: "agent/review.py", startLine: start + 1, lines, steps }, null, 2) + "\n");
console.log(`snippets: decide() lines ${start + 1}-${end}, ${steps.length} steps → ${path.relative(process.cwd(), out)}`);
