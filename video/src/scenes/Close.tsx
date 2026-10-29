import { AbsoluteFill, useCurrentFrame } from "remotion";
import { REPO_URL, SITE_URL } from "../data/links";
import { C, MONO, SANS, fade } from "../theme";

export const Close: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: SANS, color: C.ink, justifyContent: "center", alignItems: "center", gap: 20, paddingBottom: 120 }}>
      <div style={{ fontSize: 140, fontWeight: 800, letterSpacing: -4, opacity: fade(frame, 0) }}>
        <span style={{ color: C.fail }}>Red</span>2<span style={{ color: C.pass }}>Fix</span>
      </div>
      <div style={{ fontFamily: MONO, fontSize: 44, opacity: fade(frame, 20) }}>{SITE_URL}</div>
      <div style={{ fontFamily: MONO, fontSize: 36, color: C.g600, opacity: fade(frame, 30) }}>{REPO_URL}</div>
      <div style={{ fontSize: 30, color: C.g400, marginTop: 30, opacity: fade(frame, 45) }}>
        Built on NVIDIA Nemotron 3 and Nebius Token Factory, traced in LangSmith, searched with Tavily.
      </div>
    </AbsoluteFill>
  );
};
