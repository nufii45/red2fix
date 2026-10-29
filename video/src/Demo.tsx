import { AbsoluteFill, Audio, Series } from "remotion";
import { Captions } from "./components/Captions";
import { staticSrc } from "./components/Recording";
import { Bench } from "./scenes/Bench";
import { Close } from "./scenes/Close";
import { Code } from "./scenes/Code";
import { Flow } from "./scenes/Flow";
import { Limitation } from "./scenes/Limitation";
import { Live } from "./scenes/Live";
import { Title } from "./scenes/Title";
import { Verdicts } from "./scenes/Verdicts";
import { C } from "./theme";
import { SCENES, type SceneId } from "./timeline";

const VIEWS: Record<SceneId, React.FC> = { title: Title, flow: Flow, live: Live, verdicts: Verdicts, code: Code, bench: Bench, limitation: Limitation, close: Close };

export const Demo: React.FC = () => {
  const vo = staticSrc("vo.mp3");
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <Series>
        {SCENES.map(({ id, frames }) => {
          const View = VIEWS[id];
          return (
            <Series.Sequence key={id} durationInFrames={frames} name={id}>
              <View />
              <Captions scene={id} />
            </Series.Sequence>
          );
        })}
      </Series>
      {vo && <Audio src={vo} />}
    </AbsoluteFill>
  );
};
