import { AbsoluteFill, Img, OffthreadVideo, getStaticFiles, interpolate, useCurrentFrame } from "remotion";
import { C, MONO } from "../theme";
import type { Rec } from "../timeline";
import { Slate } from "./Slate";

/** public/ has this file? Read on every render so the studio picks up new recordings. */
export const staticSrc = (name: string) => getStaticFiles().find((f) => f.name === name)?.src;

/** A real screen recording from public/rec/ (.mp4, else .png), or a slate saying what to record. */
export const Recording: React.FC<{ rec: Rec }> = ({ rec }) => {
  const frame = useCurrentFrame();
  const video = staticSrc(`rec/${rec.name}.mp4`);
  const image = video ? undefined : staticSrc(`rec/${rec.name}.png`);
  if (!video && !image) return <Slate file={`rec/${rec.name}.mp4`} what={rec.what} />;

  const z = rec.zoom ?? [[0, 1, 50, 50]];
  const at = (i: number) =>
    z.length < 2 ? z[0][i] : interpolate(frame, z.map((k) => k[0]), z.map((k) => k[i]), { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const style = { width: "100%", height: "100%", objectFit: "contain" as const, transform: `scale(${at(1)})`, transformOrigin: `${at(2)}% ${at(3)}%` };

  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      {video ? <OffthreadVideo src={video} playbackRate={rec.rate} muted style={style} /> : <Img src={image!} style={style} />}
      {video && rec.rate !== 1 && (
        <div style={{ position: "absolute", top: 24, right: 24, padding: "6px 14px", borderRadius: 8, background: "rgba(0,0,0,0.75)", color: C.ink, fontFamily: MONO, fontSize: 26, fontWeight: 700 }}>
          ▶▶ {rec.rate}×
        </div>
      )}
    </AbsoluteFill>
  );
};
