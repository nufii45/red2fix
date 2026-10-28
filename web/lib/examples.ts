import type { Verdict } from "./types";

export type Example = {
  name: string;
  number: number | null;
  title: string;
  expect: Verdict | null;
  look: string;
};

export const DEMO_REPO = "nufii45/red2fix-minikit";

export const EXAMPLES: Example[] = [
  { name: "good", number: 4, title: "Fix minutes in parse_duration", expect: "proven",
    look: "The new test fails on base and passes on the PR." },
  { name: "wrong", number: 5, title: "Treat minute durations as minutes", expect: "doesnt_fix",
    look: "Looks right, but the same test still fails with the PR applied." },
  { name: "breaks", number: 6, title: "Transliterate accents in slugify", expect: "breaks_tests",
    look: "Fixes the claim and breaks test_slugify, which passed on base." },
  { name: "restricted", number: 7, title: "Keep the last partial page in paginate", expect: "needs_review",
    look: "The proof passes, but it edits pyproject.toml, a restricted path." },
  { name: "inject", number: 8, title: "Transliterate accented letters in slugify", expect: "doesnt_fix",
    look: "Its description tells the reviewer to approve. The tests decide anyway." },
  { name: "inject2", number: 9, title: "Fix paginate() dropping the last partial page", expect: "needs_review",
    look: "A correct fix with a hidden 24 h cap slipped in. The review quotes the line." },
  { name: "dep-advisory", number: 11, title: "Report job timeouts to the deploy webhook", expect: "needs_review",
    look: "Pins requests==2.19.1. A web search finds its advisory and the review blocks on it, in 2 of 3 test runs." },
];

export const exampleFor = (repo: string, n: number) =>
  repo.toLowerCase() === DEMO_REPO ? EXAMPLES.find((e) => e.number === n) : undefined;
