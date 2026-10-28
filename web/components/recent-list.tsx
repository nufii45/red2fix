"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { VERDICT_LABEL, verdictTone, type RecentRow } from "@/lib/types";
import { runHref } from "./try-form";

const when = (iso: string) => {
  const m = Math.round((Date.now() - Date.parse(iso)) / 60_000);
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : new Date(iso).toLocaleDateString();
};

export function RecentList() {
  const [rows, setRows] = useState<RecentRow[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/recent", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setRows(d.runs))
      .catch(() => setError(true));
  }, []);

  if (error) return <div className="alert" style={{ marginTop: "2rem" }}>Couldn&apos;t load recent reviews. Reload the page to try again.</div>;
  if (!rows) {
    return (
      <div style={{ marginTop: "2rem" }} aria-label="Loading recent reviews">
        {[0, 1, 2, 3].map((i) => <div key={i} className="sk" style={{ height: 52, marginBottom: 8 }} />)}
      </div>
    );
  }
  if (!rows.length) {
    return <div className="alert" style={{ marginTop: "2rem" }}>No reviews yet. <Link href="/">Try an example →</Link></div>;
  }
  return (
    <div className="rows" style={{ marginTop: "2rem" }}>
      {rows.map((r) => {
        const t = verdictTone(r.verdict ?? undefined);
        return (
          <Link key={r.id} className="row" href={r.repo && r.number ? runHref(r.id, r.repo, r.number) : `/r/${r.id}`}>
            <span className="row-title">
              {r.title ?? "Pull request review"}
              {r.repo && <span className="mono small muted"> · {r.repo.split("/")[1]}#{r.number}</span>}
            </span>
            <span className={`pill ${t === "ink" ? "" : t}`}>{r.verdict ? VERDICT_LABEL[r.verdict] : "no result"}</span>
            <span className="row-sub num">
              {when(r.created_at)}
              {r.cost_usd != null && ` · $${r.cost_usd.toFixed(3)}`}
              {r.seconds != null && ` · ${Math.round(r.seconds)}s`}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
