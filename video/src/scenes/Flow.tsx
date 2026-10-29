import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, MONO, SANS } from "../theme";

// Snake layout: 1–4 left to right, 5–8 right to left. The review pipeline (README.md "How it works"); model routing from README.md:81-82.
const STEPS: { text: string; tag: string; color?: string }[] = [
  { text: "Issue", tag: "Nano 3 · triage" },
  { text: "Test written without seeing the diff", tag: "Ultra 3 · test" },
  { text: "Fails on main", tag: "pytest + Ultra 3", color: C.fail },
  { text: "Passes on the PR", tag: "pytest", color: C.pass },
  { text: "Existing tests still pass", tag: "pytest", color: C.pass },
  { text: "Reviews the diff against .red2fix.toml", tag: "Ultra 3 · review" },
  { text: "red2fix/verdict status", tag: "GitHub check" },
  { text: "GitHub auto-merge", tag: "GitHub", color: C.pass },
];
const STEP_FRAMES = 65;

export const Flow: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: SANS, color: C.ink, padding: "120px 90px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "70px 60px", alignContent: "start" }}>
      {STEPS.map((s, i) => {
        const t = spring({ frame: frame - 20 - i * STEP_FRAMES, fps, config: { damping: 200 } });
        return (
          <div key={i} style={{ gridRow: i < 4 ? 1 : 2, gridColumn: i < 4 ? i + 1 : 8 - i, position: "relative", opacity: t, transform: `translateY(${(1 - t) * 30}px)`, border: `2px solid ${s.color ?? C.g300}`, borderRadius: 16, padding: "28px 26px", minHeight: 210, background: "#121216" }}>
            <div style={{ fontFamily: MONO, fontSize: 22, color: C.g400 }}>{i + 1}</div>
            <div style={{ fontSize: 36, fontWeight: 600, lineHeight: 1.2, marginTop: 8, color: s.color ?? C.ink }}>{s.text}</div>
            <div style={{ fontFamily: MONO, fontSize: 22, color: C.g600, marginTop: 16 }}>{s.tag}</div>
            {i < 3 && <div style={{ position: "absolute", right: -50, top: "42%", fontSize: 40, color: C.g400 }}>→</div>}
            {i === 3 && <div style={{ position: "absolute", left: "48%", bottom: -64, fontSize: 40, color: C.g400 }}>↓</div>}
            {i > 3 && i < 7 && <div style={{ position: "absolute", left: -50, top: "42%", fontSize: 40, color: C.g400 }}>←</div>}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
