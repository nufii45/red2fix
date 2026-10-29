import { AbsoluteFill, Series } from "remotion";
import { Recording } from "../components/Recording";
import { LIVE_SPLIT, REC, framesOf } from "../timeline";

export const Live: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    <Series>
      <Series.Sequence durationInFrames={LIVE_SPLIT}>
        <Recording rec={REC.tryit} />
      </Series.Sequence>
      <Series.Sequence durationInFrames={framesOf("live") - LIVE_SPLIT}>
        <Recording rec={REC.github} />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);
