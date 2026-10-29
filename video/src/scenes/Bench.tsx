import { AbsoluteFill, useCurrentFrame } from "remotion";
import { BENCH as B } from "../data/bench";
import { C, MONO, SANS, fade } from "../theme";

const TILES = [
  { big: `${B.falseApprovals} / ${B.failed}`, text: "broken patches approved (official labels)", note: `${B.falseApprovalsCleaned} of ${B.trulyFailed} on patches that fail their target tests, see bench-analysis.md`, color: C.fail },
  { big: `${B.goldProven} / ${B.gold}`, text: "correct patches proven", color: C.pass },
  { big: `${B.unprovenStored}`, text: "unproven (stored run)" },
  { big: `${B.errors}`, text: `errors (${B.errorsInfra} infra, ${B.errorsBadPatch} bad patches, ${B.errorsBudget} budget cap)` },
  { big: `$${B.medianUsd}`, text: "median cost per review" },
  { big: `${B.medianSeconds} s`, text: "median time per review" },
];

export const Bench: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: SANS, color: C.ink, padding: "60px 90px" }}>
      <div style={{ fontSize: 44, fontWeight: 700 }}>
        {B.reviews} SWE-bench Lite patches <span style={{ color: C.g400, fontWeight: 400 }}>· {B.gold} correct, {B.failed} failed</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 28, marginTop: 40 }}>
        {TILES.map((t, i) => (
          <div key={i} style={{ opacity: fade(frame, 20 + i * 25), border: `2px solid ${t.color ?? C.g300}`, borderRadius: 16, padding: "26px 30px", minHeight: 230, background: "#121216" }}>
            <div style={{ fontSize: 84, fontWeight: 800, color: t.color ?? C.ink, fontFamily: MONO }}>{t.big}</div>
            <div style={{ fontSize: 30, marginTop: 6 }}>{t.text}</div>
            {t.note && <div style={{ fontSize: 22, color: C.g600, marginTop: 10 }}>{t.note}</div>}
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 90, bottom: 150, fontFamily: MONO, fontSize: 20, color: C.g400 }}>
        bench run rv-full at 0c32486 · docs/bench-analysis.md, docs/spec/DECISIONS.md
      </div>
    </AbsoluteFill>
  );
};
