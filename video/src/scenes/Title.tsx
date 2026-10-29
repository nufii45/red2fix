import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, SANS, fade } from "../theme";

export const Title: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill style={{ background: C.bg, justifyContent: "center", alignItems: "center", fontFamily: SANS, color: C.ink }}>
      <div style={{ fontSize: 180, fontWeight: 800, letterSpacing: -6, transform: `scale(${0.9 + 0.1 * s})`, opacity: s }}>
        <span style={{ color: C.fail }}>Red</span>2<span style={{ color: C.pass }}>Fix</span>
      </div>
      <div style={{ fontSize: 52, color: C.g600, marginTop: 8, opacity: fade(frame, 60, 20) }}>from failing test to proven merge</div>
    </AbsoluteFill>
  );
};
