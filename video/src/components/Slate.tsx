import { AbsoluteFill } from "remotion";
import { C, MONO } from "../theme";

export const Slate: React.FC<{ file: string; what: string }> = ({ file, what }) => (
  <AbsoluteFill style={{ background: "#000", border: `3px dashed ${C.g300}`, justifyContent: "center", padding: 48 }}>
    <div style={{ fontFamily: MONO, color: C.fail, fontSize: 28, fontWeight: 700 }}>RECORDING NEEDED: {file}</div>
    <div style={{ fontFamily: MONO, color: C.g600, fontSize: 24, marginTop: 16 }}>{what}</div>
  </AbsoluteFill>
);
