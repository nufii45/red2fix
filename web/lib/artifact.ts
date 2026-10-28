import { strFromU8, unzipSync } from "fflate";
import type { Meta, ModelTotals, Phase, Result, Review, WebSearch } from "./types";

/** Model IDs from config.py MODELS. */
const MODEL_KEYS: Record<string, keyof ModelTotals> = {
  "nvidia/Nemotron-3-Ultra-550b-a55b": "ultra",
  "nvidia/nemotron-3-super-120b-a12b": "super",
  "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": "nano",
};

const lines = (text: string) =>
  text
    .split("\n")
    .filter((l) => l.trim())
    .flatMap((l) => {
      try {
        return [JSON.parse(l)];
      } catch {
        return [];
      }
    });

const json = <T>(text: string | undefined): T | null => {
  if (!text) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
};

export function modelTotals(ledger: string): ModelTotals {
  const totals: ModelTotals = {
    nano: { calls: 0, in_tokens: 0, out_tokens: 0, usd: 0 },
    ultra: { calls: 0, in_tokens: 0, out_tokens: 0, usd: 0 },
    super: { calls: 0, in_tokens: 0, out_tokens: 0, usd: 0 },
  };
  for (const row of lines(ledger)) {
    const k = MODEL_KEYS[row.model] ?? (Object.values(MODEL_KEYS).find((v) => String(row.model).toLowerCase().includes(v)));
    if (!k) continue;
    totals[k].calls += 1;
    totals[k].in_tokens += row.in_tokens ?? 0;
    totals[k].out_tokens += row.out_tokens ?? 0;
    totals[k].usd += row.cost_usd ?? 0;
  }
  return totals;
}

/** Files by basename, whatever folder the artifact put them in. */
export function unzip(zip: Uint8Array): Record<string, string> {
  const files: Record<string, string> = {};
  for (const [path, bytes] of Object.entries(unzipSync(zip))) {
    const name = path.split("/").pop();
    if (name && !path.endsWith("/")) files[name] = strFromU8(bytes);
  }
  return files;
}

export function parseFiles(files: Record<string, string>): Result {
  const review = json<Review>(files["review.json"]);
  const phases: Phase[] = lines(files["events.jsonl"] ?? "")
    .filter((e) => e.ev === "phase" || e.ev === "end")
    .map((e) => ({ name: e.ev === "end" ? "END" : e.name, t: e.t }));
  return {
    meta: json<Meta>(files["meta.json"]),
    review,
    review_md: files["review.md"] ?? "",
    repro: files["repro_test.py"] ?? "",
    models: modelTotals(files["ledger.jsonl"] ?? ""),
    web_searches: (review?.web_searches ?? []).filter((s): s is WebSearch => !!s && typeof s.query === "string")
      .map((s) => ({ ...s, urls: Array.isArray(s.urls) ? s.urls.filter((u) => /^https?:\/\//.test(u)) : [] })),
    trace_url: review?.trace_url ?? null,
    phases,
  };
}
