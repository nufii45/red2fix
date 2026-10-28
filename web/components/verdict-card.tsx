import { VERDICT_LABEL, verdictTone, type Result } from "@/lib/types";
import { CopyLink } from "./run-view";

const usd = (n: number) => (n === 0 ? "$0" : n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(n < 1 ? 3 : 2)}`);
const tok = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
const tone = (t: string) => (t === "ink" ? "" : t);
const shortUrl = (u: string) => {
  try {
    const url = new URL(u);
    const path = decodeURIComponent(url.pathname).replace(/\/$/, "");
    return url.hostname.replace(/^www\./, "") + (path.length > 48 ? `${path.slice(0, 46)}…` : path);
  } catch {
    return u;
  }
};

export function VerdictCard({ result, runUrl }: { result: Result; runUrl?: string }) {
  const rv = result.review!;
  const models = (["nano", "ultra", "super"] as const).map((k) => ({ k, ...result.models[k] }));
  const calls = models.reduce((a, m) => a + m.calls, 0);
  const headPassed = rv.proof.head?.startsWith("passed");

  return (
    <>
      <article className="card" aria-label="Verdict">
        <p className="label">verdict</p>
        <p className={`verdict ${tone(verdictTone(rv.verdict))}`} style={{ marginTop: "0.6rem" }}>
          {VERDICT_LABEL[rv.verdict] ?? rv.verdict}
        </p>
        {rv.verdict_reason && <p className="reason">{rv.verdict_reason}</p>}

        <dl className="kv">
          {rv.claim && (<><dt className="label">claim</dt><dd>{rv.claim}</dd></>)}
          <dt className="label">red on base</dt>
          <dd className={`evidence ${rv.proof.base?.startsWith("failed") ? "fail" : "muted"}`}>{rv.proof.base || "—"}</dd>
          <dt className="label">green on PR</dt>
          <dd className={`evidence ${headPassed ? "pass" : rv.proof.head ? "fail" : "muted"}`}>{rv.proof.head || "not run"}</dd>
          <dt className="label">new failures</dt>
          <dd className={`evidence ${rv.suite.new_failures.length ? "fail" : ""}`}>
            {rv.suite.new_failures.length ? rv.suite.new_failures.join(", ") : "none"}
          </dd>
          {rv.restricted_paths_touched.length > 0 && (
            <><dt className="label">restricted paths</dt><dd className="evidence">{rv.restricted_paths_touched.join(", ")}</dd></>
          )}
          {rv.summary && (<><dt className="label">review</dt><dd>{rv.summary}</dd></>)}
          <dt className="label">findings</dt>
          <dd>
            {rv.findings.length === 0 ? (
              <span className="muted">none</span>
            ) : (
              rv.findings.map((f, i) => (
                <div className="finding" key={i}>
                  <span className={`pill ${f.severity === "blocker" ? "inv" : ""}`}>{f.severity}</span>{" "}
                  <span className="small" style={{ fontWeight: 500 }}>{f.rule}</span>
                  {f.file && <span className="mono small muted"> · {f.file}{f.line ? `:${f.line}` : ""}</span>}
                  {f.note && <span className="note">{f.note}</span>}
                  {f.quote && <pre className="quote">{f.quote.trim()}</pre>}
                  {f.source && /^https?:\/\//.test(f.source) && (
                    <span className="small" style={{ display: "block", marginTop: "0.35rem" }}>
                      source: <a href={f.source} target="_blank" rel="noreferrer">{shortUrl(f.source)} ↗</a>
                    </span>
                  )}
                </div>
              ))
            )}
          </dd>
          <dt className="label">web searches</dt>
          <dd>
            {result.web_searches.length === 0 ? (
              <span className="muted small">{rv.web_search ? "none needed in this review" : "off for this review"}</span>
            ) : (
              result.web_searches.map((s, i) => (
                <div className="finding" key={i}>
                  <span className="pill">{s.phase.toLowerCase()}</span>{" "}
                  <span className="mono small">{s.query}</span>
                  {s.urls.length ? (
                    <ul className="links">
                      {s.urls.map((u) => (
                        <li key={u}><a href={u} target="_blank" rel="noreferrer">{shortUrl(u)} ↗</a></li>
                      ))}
                    </ul>
                  ) : (
                    <span className="note">{s.status}</span>
                  )}
                </div>
              ))
            )}
          </dd>
        </dl>
      </article>

      <h2 className="section">cost</h2>
      <div className="stats four">
        <div className="stat"><p className="label">total</p><p className="v num">{usd(rv.cost_usd)}</p></div>
        <div className="stat"><p className="label">time</p><p className="v num">{Math.round(rv.seconds)}s</p></div>
        <div className="stat"><p className="label">model calls</p><p className="v num">{calls}</p></div>
        <div className="stat"><p className="label">web searches</p><p className="v num">{result.web_searches.length}</p></div>
      </div>
      <div className="table-wrap">
        <table className="table" style={{ marginTop: "1rem" }}>
          <thead>
            <tr><th>model</th><th className="r">calls</th><th className="r">tokens in / out</th><th className="r">cost</th></tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.k}>
                <td style={{ textTransform: "capitalize" }}>{m.k}</td>
                <td className="r">{m.calls}</td>
                <td className="r">{m.calls ? `${tok(m.in_tokens)} / ${tok(m.out_tokens)}` : "—"}</td>
                <td className="r">{m.calls ? usd(m.usd) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="label" style={{ marginTop: "0.6rem" }}>
        NVIDIA Nemotron on Nebius Token Factory · budget $1 per review{result.web_searches.length > 0 && " · searches by Tavily, not in the $ total"}
      </p>

      <div className="actions">
        {result.trace_url ? (
          <a className="btn primary" href={result.trace_url} target="_blank" rel="noreferrer" title="Live traces are private to the LangSmith project">
            View trace in LangSmith, maintainers only <span className="arrow">↗</span>
          </a>
        ) : (
          <button className="btn" disabled title="Tracing isn't on for this run">No LangSmith trace for this run</button>
        )}
        {runUrl && <a className="btn" href={runUrl} target="_blank" rel="noreferrer">View workflow run <span className="arrow">↗</span></a>}
        <CopyLink />
      </div>

      <div style={{ marginTop: "2rem" }}>
        {result.repro && (
          <details>
            <summary className="label">repro test</summary>
            <pre className="code">{result.repro.trimEnd()}</pre>
          </details>
        )}
        {result.review_md && (
          <details>
            <summary className="label">review.md, the PR comment</summary>
            <pre className="code" style={{ whiteSpace: "pre-wrap" }}>{result.review_md.trimEnd()}</pre>
          </details>
        )}
      </div>
    </>
  );
}
