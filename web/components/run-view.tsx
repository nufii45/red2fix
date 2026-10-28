"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BAR, bar, clock, elapsed } from "@/lib/steps";
import type { RunState } from "@/lib/types";
import { VerdictCard } from "./verdict-card";

const ID = /^[0-9a-f]{6}[a-z2-7]{8}$/;
const NOT_FOUND_AFTER_MS = 60_000;

const ordinal = (n: number) => `${n}${n % 10 === 1 && n !== 11 ? "st" : n % 10 === 2 && n !== 12 ? "nd" : n % 10 === 3 && n !== 13 ? "rd" : "th"}`;

export function RunView({ id }: { id: string }) {
  const params = useSearchParams();
  const hint = params.get("pr"); // "owner/name#n", a display hint until the artifact confirms it
  const [run, setRun] = useState<RunState | null>(null);
  const [offline, setOffline] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [skew, setSkew] = useState(0);
  const [opened] = useState(() => Date.now());
  const runId = useRef<number | undefined>(undefined);

  const valid = ID.test(id);
  const done = run?.status === "completed" && run.result !== undefined;

  useEffect(() => {
    if (!valid || done) return;
    let stop = false;
    let delay = 2500;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const res = await fetch(`/api/review/${id}${runId.current ? `?run=${runId.current}` : ""}`, { cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const data: RunState = await res.json();
        if (stop) return;
        runId.current = data.run_id ?? runId.current;
        setSkew(Date.now() - Date.parse(data.now));
        setRun(data);
        setOffline(false);
        delay = 2500;
        if (data.status === "completed" && data.result !== undefined) return;
        if (!data.found && Date.now() - opened > NOT_FOUND_AFTER_MS) return;
      } catch {
        if (stop) return;
        setOffline(true);
        delay = Math.min(delay * 2, 30_000);
      }
      timer = setTimeout(poll, delay);
    };
    poll();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [id, valid, done, opened]);

  useEffect(() => {
    if (done) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [done]);

  if (!valid) return <Missing text="That isn't a review link. Check that you copied all of it." />;

  const meta = run?.result?.meta;
  const [hintRepo, hintN] = hint?.split("#") ?? [];
  const repo = meta?.repo ?? hintRepo;
  const number = meta?.number ?? (hintN ? Number(hintN) : undefined);
  const prLink = meta?.pr_url ?? (repo && number ? `https://github.com/${repo}/pull/${number}` : null);

  const header = (
    <header>
      <p className="label">review · <span className="mono" style={{ textTransform: "none" }}>{id}</span></p>
      <h1 style={{ fontSize: "1.5rem", marginTop: "0.5rem" }}>
        {meta?.title || (repo && number ? `${repo.split("/")[1]} #${number}` : "Pull request review")}
      </h1>
      {prLink && (
        <p className="small muted" style={{ marginTop: "0.35rem" }}>
          <a href={prLink} target="_blank" rel="noreferrer">{repo}#{number} ↗</a>
        </p>
      )}
    </header>
  );

  if (!run) {
    return (
      <>
        {header}
        <div className="steps" aria-hidden>{BAR.map((b) => <span key={b} className="sk" style={{ width: 84, height: 25, borderRadius: 999 }} />)}</div>
        <div className="sk" style={{ height: 260, marginTop: "1.5rem", borderRadius: 16 }} aria-label="Loading the review" />
        {offline && <p className="label" style={{ marginTop: "1rem" }}>Can&apos;t reach the server. Retrying…</p>}
      </>
    );
  }

  if (!run.found) {
    const waited = now - opened > NOT_FOUND_AFTER_MS;
    return waited ? (
      <Missing text="No review with this id. It may be older than GitHub keeps runs, or the link is wrong." />
    ) : (
      <>
        {header}
        <StepBar run={run} now={now - skew} />
        <p className="label" style={{ marginTop: "0.75rem" }}>Waiting for GitHub to start the run…</p>
      </>
    );
  }

  const secs = elapsed(run, now - skew);
  const status =
    run.status === "queued"
      ? `${run.ahead ? `${ordinal(run.ahead + 1)} in line` : "next in line"} · ${clock(secs)} waiting`
      : run.status === "in_progress"
        ? `${clock(secs)} elapsed`
        : `finished · ${clock(secs)} total`;

  return (
    <>
      {header}
      <StepBar run={run} now={now - skew} />
      <p className="label num" style={{ marginTop: "0.75rem" }} aria-live="polite">
        {status}
        {offline && " · reconnecting…"}
      </p>
      {run.status === "completed" ? (
        run.result?.review ? (
          <VerdictCard result={run.result} runUrl={run.run_url} />
        ) : (
          <div className="card">
            <p className="verdict">Error</p>
            <p className="reason">The run finished without a review. The workflow log says why.</p>
            <div className="actions">
              {run.run_url && <a className="btn" href={run.run_url} target="_blank" rel="noreferrer">View workflow run <span className="arrow">↗</span></a>}
            </div>
          </div>
        )
      ) : (
        <Pending run={run} />
      )}
    </>
  );
}

function StepBar({ run, now }: { run: RunState; now: number }) {
  const b = bar(run, now);
  return (
    <>
      <ol className="steps" aria-label="Progress">
        {BAR.map((name, i) => {
          const cls = b.failedAt === i ? "err" : i < b.current ? "done" : i === b.current ? "now" : "";
          const t = b.seconds[i];
          return (
            <li key={name} className={`step ${cls}`} aria-current={i === b.current ? "step" : undefined}>
              {name}
              {t != null && t >= 0.5 && <span className="t num">{Math.round(t)}s</span>}
            </li>
          );
        })}
      </ol>
      {b.estimated && <p className="label" style={{ marginTop: "0.5rem", color: "var(--g400)" }}>steps inside the review are estimated from elapsed time</p>}
    </>
  );
}

function Pending({ run }: { run: RunState }) {
  return (
    <div className="card" aria-busy>
      <p className="label">verdict</p>
      <div className="sk" style={{ height: 44, width: "55%", marginTop: "0.75rem" }} />
      <div className="sk" style={{ height: 14, width: "80%", marginTop: "1rem" }} />
      <div className="sk" style={{ height: 14, width: "65%", marginTop: "0.5rem" }} />
      <p className="small muted" style={{ marginTop: "1.25rem" }}>
        {run.status === "queued"
          ? "Reviews run one at a time. This one starts when the one ahead finishes."
          : "You can close this page. The link keeps working, and the verdict will be here."}
      </p>
      <div className="actions">
        {run.run_url && <a className="btn" href={run.run_url} target="_blank" rel="noreferrer">View workflow run <span className="arrow">↗</span></a>}
        <CopyLink />
      </div>
    </div>
  );
}

export function CopyLink() {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="btn"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(window.location.href);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {
          window.prompt("Copy this link", window.location.href);
        }
      }}
    >
      {copied ? "Copied" : "Copy link"}
    </button>
  );
}

function Missing({ text }: { text: string }) {
  return (
    <>
      <h1 className="title">not found</h1>
      <p className="lede">{text}</p>
      <p style={{ marginTop: "1.5rem" }}><Link href="/">Start a review →</Link></p>
    </>
  );
}
