import { TryForm } from "@/components/try-form";

export default function Home() {
  return (
    <div className="col">
      <section className="hero">
        <h1 className="title">try it</h1>
        <p className="lede">
          Paste a pull request. Red2Fix writes a test from what it claims to fix without seeing the diff, shows the
          test fail on the base branch and pass on the PR, then reviews the change.
        </p>
      </section>
      <TryForm />
      <h2 className="section">02 — how it works</h2>
      <div className="how">
        <p><span className="k fail">red</span><span>A test written from the PR&apos;s claim fails on the base branch, so the bug is real.</span></p>
        <p><span className="k pass">green</span><span>The same test passes with the PR applied and no other test breaks. The review can only make that verdict stricter.</span></p>
      </div>
    </div>
  );
}
