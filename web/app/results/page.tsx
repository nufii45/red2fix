import type { Metadata } from "next";
import bench from "@/public/data/bench.json";
import { VERDICT_LABEL, verdictTone, type Verdict } from "@/lib/types";

export const metadata: Metadata = { title: "Results" };

const ORDER: Verdict[] = ["proven", "needs_review", "unproven", "doesnt_fix", "breaks_tests", "error"];
const short = (id: string) => id.replace(/^[^_]+__/, "");

function V({ v }: { v?: string }) {
  if (!v) return <span className="muted">—</span>;
  const t = verdictTone(v);
  return <span className={t === "ink" ? "" : t}>{VERDICT_LABEL[v as Verdict] ?? v}</span>;
}

export default function Results() {
  const b = bench;
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
          SWE-bench result. Under them Red2Fix approved two:{" "}
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
        errors, 4 come from running amd64 images under emulation, 2 from patches that don&apos;t apply with git apply,
        and 3 from the $1 budget cap.
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
      <p className="small muted" style={{ marginTop: "0.75rem" }}>
        Model calls: Ultra {b.calls.ultra}, Nano {b.calls.nano}, Super {b.calls.super}. Reviews of the small demo
        pull requests cost about $0.02–0.04 each.
      </p>

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
