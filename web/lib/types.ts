export type Verdict = "proven" | "needs_review" | "unproven" | "doesnt_fix" | "breaks_tests" | "error";

export const VERDICT_LABEL: Record<Verdict, string> = {
  proven: "Proven",
  needs_review: "Needs review",
  unproven: "Unproven",
  doesnt_fix: "Doesn't fix",
  breaks_tests: "Breaks tests",
  error: "Error",
};

/** Red and green are reserved for verdicts; everything else stays ink. */
export const verdictTone = (v: Verdict | string | undefined) =>
  v === "proven" ? "pass" : v === "doesnt_fix" || v === "breaks_tests" ? "fail" : "ink";

export type Finding = {
  rule?: string;
  severity?: "blocker" | "warning" | "info";
  file?: string;
  line?: number;
  note?: string;
  quote?: string;
  source?: string; // the searched URL an advisory finding cites
};

export type Review = {
  verdict: Verdict;
  verdict_reason: string | null;
  claim: string;
  summary: string;
  spec_source: string;
  proof: { repro_test: string | null; base: string | null; head: string | null; result?: string };
  suite: { new_failures: string[] };
  findings: Finding[];
  restricted_paths_touched: string[];
  cost_usd: number;
  seconds: number;
  web_search?: boolean;
  web_searches?: WebSearch[];
  trace_url?: string;
};

/** One Tavily search, as agent/search.py logs it in review.json "web_searches". */
export type WebSearch = { phase: string; query: string; urls: string[]; status: string };

export type ModelTotals = Record<"nano" | "ultra" | "super", { calls: number; in_tokens: number; out_tokens: number; usd: number }>;

export type Meta = {
  request_id: string;
  pr_url: string;
  repo: string;
  number: number;
  title: string;
  base_sha?: string;
  head_sha?: string;
  spec_source?: string;
};

export type Phase = { name: string; t: number };

export type Result = {
  meta: Meta | null;
  review: Review | null;
  review_md: string;
  repro: string;
  models: ModelTotals;
  web_searches: WebSearch[];
  trace_url: string | null;
  phases: Phase[];
};

export type Step = { name: string; status: string; conclusion: string | null; started_at: string | null; completed_at: string | null };

export type RunState = {
  id: string;
  found: boolean;
  run_id?: number;
  status?: "queued" | "in_progress" | "completed";
  conclusion?: string | null;
  ahead?: number;
  created_at?: string;
  started_at?: string | null;
  updated_at?: string;
  now: string;
  run_url?: string;
  steps: Step[];
  result?: Result | null;
};

export type RecentRow = {
  id: string;
  created_at: string;
  pr_url: string | null;
  repo: string | null;
  number: number | null;
  title: string | null;
  verdict: Verdict | null;
  cost_usd: number | null;
  seconds: number | null;
};
