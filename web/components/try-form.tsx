"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DEMO_REPO, EXAMPLES } from "@/lib/examples";
import { VERDICT_LABEL, verdictTone } from "@/lib/types";
import { refreshLimits, useLimits } from "./use-limits";

type Pr = { number: number; title: string; user: string; html_url: string };
type Err = { reason: string; message: string; waiting?: string };
type Picker = { repo: string; prs: Pr[] };

export const runHref = (id: string, repo: string, n: number) => `/r/${id}?pr=${encodeURIComponent(`${repo}#${n}`)}`;

export function TryForm({ offline = false }: { offline?: boolean }) {
  const router = useRouter();
  const { limits } = useLimits();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<Err | null>(null);
  const [picker, setPicker] = useState<Picker | null>(null);

  async function submit(value: string, key = "form") {
    if (!value.trim()) {
      setErr({ reason: "bad_url", message: "Paste a link like github.com/owner/repo/pull/12." });
      return;
    }
    setBusy(key);
    setErr(null);
    try {
      const res = await fetch("/api/review", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: value }) });
      const data = await res.json().catch(() => ({ error: { reason: "github", message: "Something went wrong. Try again." } }));
      if (!res.ok) {
        setErr(data.error);
        refreshLimits();
        return;
      }
      if (data.kind === "repo") {
        setPicker({ repo: data.repo, prs: data.prs });
        return;
      }
      const m = value.match(/github\.com\/([^/]+\/[^/]+)\/pulls?\/(\d+)/i);
      router.push(m ? runHref(data.id, m[1], Number(m[2])) : `/r/${data.id}`);
    } catch {
      setErr({ reason: "network", message: "Couldn't reach the server. Check your connection and try again." });
    } finally {
      setBusy(null);
    }
  }

  const out = limits?.remaining === 0;

  return (
    <>
      {offline ? (
        <div className="alert" role="status">
          <strong>Live reviews are offline.</strong> The examples below replay recorded reviews; no new review runs.
        </div>
      ) : (
        <>
      <form
        className="field"
        onSubmit={(e) => {
          e.preventDefault();
          setPicker(null);
          submit(url);
        }}
      >
        <input
          aria-label="GitHub repo or pull request URL"
          placeholder="Paste a GitHub repo or pull request URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
        />
        <button className="btn primary" disabled={!!busy || out}>
          {busy === "form" ? "Starting…" : "Review"}
        </button>
      </form>
      <div className="note">
        <span className="label">Reviews run the pull request&apos;s code on a GitHub-hosted runner.</span>
        <span className="label num">
          {limits ? `${limits.remaining} of ${limits.cap} left today` : "\u00a0"}
        </span>
      </div>

      {err && <Alert err={err} />}
      {out && !err && (
        <div className="alert" role="status">Today&apos;s {limits!.cap} free reviews are used up. They reset at 00:00 UTC.</div>
      )}
        </>
      )}
      {offline && err && <Alert err={err} />}

      {picker && (
        <div style={{ marginTop: "1.5rem" }}>
          <p className="label" style={{ marginBottom: "0.5rem" }}>Open pull requests in {picker.repo}</p>
          {picker.prs.length === 0 ? (
            <div className="alert">No open pull requests in {picker.repo}. Paste a pull request link instead.</div>
          ) : (
            <div className="rows">
              {picker.prs.map((p) => (
                <button key={p.number} className="row" disabled={!!busy || out} onClick={() => submit(p.html_url, `pick-${p.number}`)}>
                  <span className="row-title">#{p.number} {p.title}</span>
                  <span className="label">{busy === `pick-${p.number}` ? "starting…" : <>review <span className="arrow">↗</span></>}</span>
                  <span className="row-sub">by {p.user}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <h2 className="section">01 — examples</h2>
      <p className="muted small" style={{ marginBottom: "1rem" }}>
        Seven pull requests on <a href={`https://github.com/${DEMO_REPO}/pulls`} target="_blank" rel="noreferrer">{DEMO_REPO} ↗</a>, each
        built to show one verdict. One click {offline ? "replays its recorded review" : "starts a review"}.
      </p>
      <div className="rows">
        {EXAMPLES.map((e) => {
          const key = `ex-${e.name}`;
          const href = e.number ? `https://github.com/${DEMO_REPO}/pull/${e.number}` : "";
          return (
            <button
              key={e.name}
              className={`row${e.number ? "" : " static"}`}
              disabled={!e.number || !!busy || out}
              onClick={() => submit(href, key)}
              aria-label={e.number ? `Review example ${e.name}, pull request ${e.number}` : `${e.name}, not available yet`}
            >
              <span className="row-title">
                <span className="mono small muted">{e.number ? `#${e.number} ` : ""}{e.name}</span> · {e.title}
              </span>
              {e.expect ? (
                <span className={`pill ${verdictTone(e.expect) === "ink" ? "" : verdictTone(e.expect)}`}>
                  {busy === key ? "starting…" : `expect ${VERDICT_LABEL[e.expect].toLowerCase()}`}
                </span>
              ) : (
                <span className="pill">not yet</span>
              )}
              <span className="row-sub">{e.look}</span>
            </button>
          );
        })}
      </div>
      {limits?.simulated && !offline && (
        <p className="label sim">Local mode: GitHub is simulated with recorded demo reviews. No model calls are made.</p>
      )}
    </>
  );
}

function Alert({ err }: { err: Err }) {
  return (
    <div className="alert" role="alert">
      {err.message}{" "}
      {err.reason === "not_allowlisted" && <Link href="/install">Use it on your own repo →</Link>}
      {err.reason === "one_waiting" && err.waiting && <Link href={`/r/${err.waiting}`}>Watch the waiting review →</Link>}
    </div>
  );
}
