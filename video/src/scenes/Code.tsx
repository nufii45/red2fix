import { AbsoluteFill, useCurrentFrame } from "remotion";
import snippet from "../data/snippets.json";
import { C, MONO, SANS, fade } from "../theme";

const START = 40;
const PER_STEP = 60;
const DONE = START + snippet.steps.length * PER_STEP;

export const Code: React.FC = () => {
  const frame = useCurrentFrame();
  const step = frame < START || frame >= DONE ? -1 : Math.floor((frame - START) / PER_STEP);
  const cur = snippet.steps[step];
  const lit = (i: number) => (cur ? i >= cur.from && i <= cur.to : frame >= DONE);
  // Distinct labels in order; the two needs_review branches share one.
  const chain = [...new Set(snippet.steps.map((s) => s.label))];
  return (
    <AbsoluteFill style={{ background: C.bg, padding: "36px 70px", fontFamily: SANS, color: C.ink }}>
      <div style={{ height: 56, fontSize: 30, fontWeight: 600 }}>
        {frame < DONE ? (
          chain.map((l, i) => (
            <span key={l} style={{ color: cur?.label === l ? (l === "proven" ? C.pass : C.fail) : C.g400 }}>
              {i > 0 && <span style={{ color: C.g300 }}> &gt; </span>}
              {l}
            </span>
          ))
        ) : (
          <span style={{ opacity: fade(frame, DONE) }}>pytest decides proof; the model can only make it stricter.</span>
        )}
      </div>
      <div style={{ fontFamily: MONO, fontSize: 19, lineHeight: "27px", whiteSpace: "pre" }}>
        {snippet.lines.map((l, i) => (
          <div key={i} style={{ color: lit(i) ? C.ink : C.g400, opacity: lit(i) ? 1 : 0.45, background: cur && lit(i) ? "rgba(255,255,255,0.06)" : undefined }}>
            <span style={{ display: "inline-block", width: 56, color: C.g400 }}>{snippet.startLine + i}</span>
            {l}
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", top: 44, right: 70, fontFamily: MONO, fontSize: 20, color: C.g400 }}>{snippet.file}</div>
    </AbsoluteFill>
  );
};
