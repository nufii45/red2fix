import type { Metadata } from "next";
import bench from "@/public/data/bench.json";
import demos from "@/public/data/demos.json";
import { DEMO_REPO, EXAMPLES } from "@/lib/examples";
import { prUrl } from "@/lib/parse-url";
import { VERDICT_LABEL, verdictTone, type Verdict } from "@/lib/types";

export const metadata: Metadata = { title: "Results" };

const ORDER: Verdict[] = ["proven", "needs_review", "unproven", "doesnt_fix", "breaks_tests", "error"];
const short = (id: string) => id.replace(/^[^_]+__/, "");
const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

function V({ v }: { v?: string }) {
  if (!v) return <span className="muted">—</span>;
  const t = verdictTone(v);
  return <span className={t === "ink" ? "" : t}>{VERDICT_LABEL[v as Verdict] ?? v}</span>;
}

export default function Results() {
  const b = bench;
  const models = Object.entries(b.cost_by_model as Record<string, { calls: number; usd: number }>);
  const demoUsd = demos.map((d) => d.cost_usd);
  return (
    <div className="col wide">
      <h1 className="title">results</h1>
      <p className="lede">
        Red2Fix reviewed {b.reviews} patches from SWE-bench Lite: the correct patch for each of {b.gold.total} frozen
        issues, and one patch per issue that a public submission got wrong. The measure that matters most is how
        often a wrong patch gets approved.
      </p>

      <div className="stats four" style={{ marginTop: "2.5rem" }}>
        <div className="stat">
          <p className="label">false approvals, original labels</p>
          <p className="v num">{b.original.false_approvals.length} of {b.original.failed_total}</p>
        </div>
        <div className="stat">
          <p className="label">false approvals, cleaned labels</p>
          <p className="v num">{b.cleaned.false_approvals.length} of {b.cleaned.failed_total}</p>
        </div>
        <div className="stat">
          <p className="label">correct patches approved</p>
          <p className="v num">{b.gold.approvals} of {b.gold.total}</p>
        </div>
        <div className="stat">
          <p className="label">median per review</p>
          <p className="v num">${b.median_usd.toFixed(2)}</p>
        </div>
      </div>

      <h2 className="section">01 — two label views</h2>
      <div className="prose">
        <p>
          <strong>Original labels</strong> take each wrong patch&apos;s status from its submitter&apos;s official
          SWE-bench result. Under them Red2Fix approved {b.original.false_approvals.length}:{" "}
          {b.original.false_approvals.map((id, i) => (
            <span key={id}><code>{short(id)}</code>{i < b.original.false_approvals.length - 1 ? " and " : "."}</span>
          ))}
        </p>
        <p>
          Both of those patches pass every official FAIL_TO_PASS test. They were marked unresolved only because
          network tests (httpbin) failed in the submitters&apos; runs. <strong>Cleaned labels</strong> count a
          patch as wrong only if a FAIL_TO_PASS test failed in its official report, which leaves {b.cleaned.failed_total}{" "}
          truly wrong patches and {b.cleaned.false_approvals.length} approvals. That rule was written after looking at
          the results, so both views are shown.
        </p>
      </div>

      <h2 className="section">02 — every verdict</h2>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>verdict</th><th className="r">correct patches</th><th className="r">wrong patches</th></tr>
          </thead>
          <tbody>
            {ORDER.map((v) => (
              <tr key={v}>
                <td><V v={v} /></td>
                <td className="r num">{(b.verdicts.gold as Record<string, number>)[v] ?? 0}</td>
                <td className="r num">{(b.verdicts.failed as Record<string, number>)[v] ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted" style={{ marginTop: "0.75rem" }}>
        Red2Fix fails closed: when it can&apos;t prove a patch, it says unproven instead of approving. Of the {b.errors}{" "}
        errors:{" "}
        {Object.entries(b.errors_by_cause).map(([cause, n], i, all) => (
          <span key={cause}>{n} {cause}{i < all.length - 1 ? ", " : "."}</span>
        ))}
      </p>

      <h2 className="section">03 — method</h2>
      <div className="prose">
        <p>
          For each patch, Red2Fix wrote a test from the issue text alone, without seeing the patch, and kept it only
          if it failed on the base commit for the reason the issue describes. It then applied the patch, ran that
          test and the instance&apos;s existing tests, and let the Nemotron review only make the verdict stricter.
          Ground truth is SWE-bench Lite&apos;s official hidden tests, which Red2Fix never sees.
        </p>
      </div>

      <h2 className="section">04 — cost</h2>
      <div className="stats">
        <div className="stat"><p className="label">median</p><p className="v num">${b.median_usd.toFixed(2)}</p><p className="label">per review</p></div>
        <div className="stat"><p className="label">median time</p><p className="v num">{Math.round(b.median_s)}s</p><p className="label">per review</p></div>
        <div className="stat"><p className="label">all {b.reviews}</p><p className="v num">${b.total_usd.toFixed(2)}</p><p className="label">total</p></div>
      </div>
      <div className="table-wrap" style={{ marginTop: "1.5rem" }}>
        <table className="table">
          <thead>
            <tr><th>model</th><th className="r">calls</th><th className="r">cost</th><th style={{ width: "35%" }}>share</th></tr>
          </thead>
          <tbody>
            {models.map(([m, c]) => (
              <tr key={m}>
                <td>Nemotron {cap(m)}</td>
                <td className="r num">{c.calls}</td>
                <td className="r num">${c.usd.toFixed(c.usd < 0.01 ? 4 : 2)}</td>
                <td aria-hidden="true">
                  <span style={{ display: "block", height: 6, minWidth: 2, width: `${(100 * c.usd) / b.total_usd}%`, background: "var(--ink)" }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="section">05 — demo pull requests</h2>
      <p className="small muted">
        The recorded reviews behind the examples on the home page, ${Math.min(...demoUsd).toFixed(2)}–$
        {Math.max(...demoUsd).toFixed(2)} each.
      </p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>PR</th><th>verdict</th><th className="r">cost</th><th className="r">time</th><th className="r">searches</th><th>trace</th></tr>
          </thead>
          <tbody>
            {demos.map((d) => {
              const e = EXAMPLES.find((x) => x.name === d.name);
              return (
                <tr key={d.name}>
                  <td>{e?.number ? <a href={prUrl(DEMO_REPO, e.number)} target="_blank" rel="noreferrer">#{e.number} {d.name}</a> : d.name}</td>
                  <td><V v={d.verdict} /></td>
                  <td className="r num">${d.cost_usd.toFixed(3)}</td>
                  <td className="r num">{Math.round(d.seconds)}s</td>
                  <td className="r num">{d.searches}</td>
                  <td>{d.trace_url ? <a href={d.trace_url} target="_blank" rel="noreferrer">LangSmith ↗</a> : <span className="muted">—</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <details style={{ marginTop: "2.5rem" }}>
        <summary className="label">all {b.instances.length} instances</summary>
        <div className="table-wrap">
          <table className="table" style={{ marginBottom: "1rem" }}>
            <thead>
              <tr><th>instance</th><th>correct patch</th><th>wrong patch</th><th className="r">cost</th></tr>
            </thead>
            <tbody>
              {b.instances.map((i) => (
                <tr key={i.id}>
                  <td className="mono" style={{ fontSize: 12 }}>{short(i.id)}</td>
                  <td><V v={i.gold?.verdict} /></td>
                  <td><V v={i.failed?.verdict} />{i.failed && !i.failed.truly_failed && <span className="label"> · label noise</span>}</td>
                  <td className="r num">${((i.gold?.cost_usd ?? 0) + (i.failed?.cost_usd ?? 0)).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="label" style={{ marginTop: "1.5rem" }}>
        Frozen run {b.run} at commit {b.commit} ·{" "}
        <a href="https://github.com/nufii45/red2fix/blob/main/docs/bench-analysis.md" target="_blank" rel="noreferrer">full analysis ↗</a>
      </p>
    </div>
  );
}
