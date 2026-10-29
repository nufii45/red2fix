import { AbsoluteFill, useCurrentFrame } from "remotion";
import { BENCH as B } from "../data/bench";
import { C, MONO, SANS, fade } from "../theme";

export const Limitation: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: SANS, color: C.ink, padding: "140px 140px", gap: 24 }}>
      <div style={{ fontSize: 36, color: C.g400, opacity: fade(frame, 0) }}>One honest limitation</div>
      <div style={{ fontSize: 140, fontWeight: 800, color: C.fail, opacity: fade(frame, 15) }}>
        {B.goldWrongExpected} of {B.gold}
      </div>
      <div style={{ fontSize: 48, maxWidth: 1500, lineHeight: 1.25, opacity: fade(frame, 30) }}>
        correct patches were rejected because the test Red2Fix wrote expected the wrong value.
      </div>
      <div style={{ fontFamily: MONO, fontSize: 20, color: C.g400, opacity: fade(frame, 30) }}>docs/bench-analysis.md §4</div>
    </AbsoluteFill>
  );
};
