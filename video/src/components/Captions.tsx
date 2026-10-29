import { AbsoluteFill, useCurrentFrame } from "remotion";
import { CAPTIONS } from "../data/captions";
import { C, SANS } from "../theme";
import type { SceneId } from "../timeline";

export const Captions: React.FC<{ scene: SceneId }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const cap = CAPTIONS.find((c) => c.scene === scene && frame >= c.from && frame < c.to);
  if (!cap) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 48 }}>
      <div style={{ maxWidth: 1500, padding: "12px 28px", borderRadius: 10, background: "rgba(0,0,0,0.78)", color: C.ink, fontFamily: SANS, fontSize: 38, fontWeight: 600, lineHeight: 1.3, textAlign: "center" }}>
        {cap.text}
      </div>
    </AbsoluteFill>
  );
};
