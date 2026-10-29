import type { SceneId } from "../timeline";

// The voice-over script. from/to are frames from the start of the scene, so retiming a scene moves its captions.
export type Caption = { scene: SceneId; from: number; to: number; text: string };

export const CAPTIONS: Caption[] = [
  { scene: "title", from: 20, to: 350, text: "AI review bots give opinions. Nobody checks the PR actually does what it claims." },
  { scene: "flow", from: 0, to: 230, text: "Red2Fix proves it. It writes a test from the issue without seeing the code," },
  { scene: "flow", from: 230, to: 450, text: "shows it fails on main and passes on the PR, checks nothing else broke," },
  { scene: "flow", from: 450, to: 680, text: "then reviews the diff." },
  { scene: "live", from: 0, to: 150, text: "Paste a PR. Nemotron 3 Nano triages the issue: is the claim testable?" },
  { scene: "live", from: 150, to: 360, text: "Nemotron 3 Ultra writes a test from the issue alone. It never sees the diff." },
  { scene: "live", from: 360, to: 540, text: "Red on base: the test fails on main, and Ultra checks it fails for the right reason." },
  { scene: "live", from: 540, to: 720, text: "Green on the PR, and the existing suite still passes. Then Ultra reviews the diff against the repo's policy." },
  { scene: "live", from: 720, to: 900, text: "Verdict: proven, with what the review cost." },
  { scene: "live", from: 900, to: 1340, text: "On GitHub, red2fix/verdict goes green and auto-merge takes it from there." },
  { scene: "verdicts", from: 0, to: 180, text: "Wrong fix: the test still fails." },
  { scene: "verdicts", from: 180, to: 360, text: "Broken suite: here's the failing test." },
  { scene: "verdicts", from: 360, to: 560, text: "This one says 'pre-approved' and hides an unrelated change." },
  { scene: "verdicts", from: 560, to: 740, text: "This one pins a library version with a known advisory." },
  { scene: "code", from: 0, to: 200, text: "The verdict is plain code. Proof comes from pytest." },
  { scene: "code", from: 200, to: 590, text: "The model can add blockers, never remove them, so a prompt injection can't talk its way to a ✅." },
  { scene: "bench", from: 0, to: 400, text: "On 40 real SWE-bench patches it's conservative by design: it would rather say 'unproven' than approve." },
  { scene: "bench", from: 400, to: 740, text: "Median 46 cents and about three minutes per review on Token Factory." },
  { scene: "limitation", from: 0, to: 220, text: "The proof is only as strong as the test it writes." },
  { scene: "limitation", from: 220, to: 440, text: "When the test is wrong, Red2Fix blocks a good PR. It doesn't approve a bad one." },
  { scene: "close", from: 30, to: 440, text: "Red2Fix: from failing test to proven merge." },
];
