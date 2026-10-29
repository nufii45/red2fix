import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Recording } from "../components/Recording";
import { CAPTIONS } from "../data/captions";
import { C, SANS, fade } from "../theme";
import { REC } from "../timeline";

const CARDS = [
  { label: "❌ Doesn't fix", color: C.fail, rec: REC.wrong },
  { label: "❌ Breaks tests", color: C.fail, rec: REC.breaks },
  { label: "🔶 Needs review", color: C.g600, rec: REC.inject2 },
  { label: "🔶 Needs review", color: C.g600, rec: REC.depAdvisory },
];

export const Verdicts: React.FC = () => {
  const frame = useCurrentFrame();
  // The card being narrated is lit; its caption is the i-th of this scene.
  const caps = CAPTIONS.filter((c) => c.scene === "verdicts");
  const active = caps.findIndex((c) => frame >= c.from && frame < c.to);
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: SANS, padding: "70px 60px 190px", flexDirection: "row", gap: 30 }}>
      {CARDS.map((c, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", opacity: fade(frame, i * 12) * (active < 0 || active === i ? 1 : 0.35) }}>
          <div style={{ fontSize: 34, fontWeight: 700, color: c.color, marginBottom: 16 }}>{c.label}</div>
          <div style={{ position: "relative", flex: 1, borderRadius: 12, overflow: "hidden", border: `2px solid ${active === i ? c.color : C.g300}` }}>
            <Recording rec={c.rec} />
          </div>
        </div>
      ))}
    </AbsoluteFill>
  );
};
