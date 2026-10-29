// Retime a scene by changing its frames here (30 fps). The composition length is the sum.
export const FPS = 30;

export const SCENES = [
  { id: "title", frames: 360 }, // 0:00–0:12
  { id: "flow", frames: 690 }, // 0:12–0:35
  { id: "live", frames: 1350 }, // 0:35–1:20
  { id: "verdicts", frames: 750 }, // 1:20–1:45
  { id: "code", frames: 600 }, // 1:45–2:05
  { id: "bench", frames: 750 }, // 2:05–2:30
  { id: "limitation", frames: 450 }, // 2:30–2:45
  { id: "close", frames: 450 }, // 2:45–3:00
] as const;

export type SceneId = (typeof SCENES)[number]["id"];
export const TOTAL_FRAMES = SCENES.reduce((n, s) => n + s.frames, 0);
export const framesOf = (id: SceneId) => SCENES.find((s) => s.id === id)!.frames;

// One entry per recording in public/rec/. The file may be .mp4 or .png (tried in that order).
// rate: playbackRate Remotion applies, and the ▶▶ badge shows the same value.
// zoom: [frame within the clip, scale, focus x %, focus y %]; tune after recording.
export type Rec = { name: string; what: string; rate: number; zoom?: [number, number, number, number][] };

export const LIVE_SPLIT = 900; // frames of the live scene given to 01-tryit; the rest go to 02-github

export const REC = {
  tryit: {
    name: "01-tryit",
    what: "try-it site: paste the minikit PR, phases tick, verdict and cost appear",
    rate: 6,
    // shortcut: placeholder focus on the cost line, set x/y once the recording exists.
    zoom: [[0, 1, 50, 50], [700, 1, 50, 50], [760, 1.8, 50, 80], [900, 1.8, 50, 80]],
  },
  github: {
    name: "02-github",
    what: "PR checks: red2fix/verdict green, auto-merge fires",
    rate: 1,
    // shortcut: placeholder focus on the status check, set x/y once the recording exists.
    zoom: [[0, 1, 50, 50], [90, 1, 50, 50], [150, 1.8, 50, 70], [450, 1.8, 50, 70]],
  },
  wrong: { name: "03-wrong", what: "Doesn't fix: the repro still fails on the PR", rate: 1 },
  breaks: { name: "04-breaks", what: "Breaks tests: the failing suite test", rate: 1 },
  inject2: { name: "05-inject2", what: "Needs review: 'pre-approved' PR hiding the 24 h cap", rate: 1 },
  depAdvisory: { name: "06-dep-advisory", what: "Needs review: the sourced advisory from Tavily", rate: 1 },
} satisfies Record<string, Rec>;
