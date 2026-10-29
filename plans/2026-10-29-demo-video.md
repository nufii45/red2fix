# Demo video with Remotion (Prompt 10)

## Context
Red2Fix needs a 3:00 hackathon demo video. Remotion draws the cards, the diagram, the code, the numbers and the captions. Every product shot is a real screen recording dropped into `video/public/rec/`. Code and numbers are pulled from the repo, never retyped. Missing recordings render as slates, so the whole timeline can be previewed before anything is recorded.

State found: `video/` already has the blank Remotion template (pnpm `node_modules`, Remotion **4.0.539** pinned exactly, `@remotion/google-fonts` installed, `MyComp` 1280×720). There's no `.vercelignore`, and `vercel.json` builds only `web/`, so `video/` is already out of the web build. Node is 24.18, which runs `.ts` scripts natively, so no `tsx` is needed. `web/public` has no logo, so the title is text only.

## Number and wording corrections (agreed with the user)
- **Scene 7:** "5 of the 20 correct patches were rejected because the test Red2Fix wrote expected the wrong value" (bench-analysis.md §4, "Wrong expected value: 5"). Not 7: 7 is all gold doesnt_fix.
- **Scene 6:** 12 unproven, 9 errors, $0.46 and 198 s are cited from `docs/spec/DECISIONS.md:41` and `README.md:90`, because bench-analysis.md doesn't contain them. The errors tile reads "9 errors (4 infra, 2 bad patches, 3 budget cap)" (DECISIONS.md, the "9 errors split three ways" line). The unproven tile reads "12 unproven (stored run)". The rest come from bench-analysis.md: 40 = 20 gold + 20 failed, 2/20 false approvals, 0/16 cleaned, 3/20 gold proven.
- **Scene 5 callout:** "error > breaks_tests > doesnt_fix > unproven (needs_review if a blocker) > needs_review > proven", matching `decide()` as it is now.

## Files
```
video/
  package.json        rename to red2fix-video; add "snippets": "node scripts/snippets.ts"; delete package-lock.json (pnpm only)
  .gitignore          + public/rec/ (out/ is already ignored here and at the root)
  RECORDING.md        recording checklist
  scripts/snippets.ts reads ../agent/review.py, writes src/data/snippets.json; exits 1 on any missing marker
  src/index.ts, Root.tsx       one <Composition id="Red2FixDemo" 1920×1080 30fps>, duration = sum of timeline
  src/timeline.ts     SCENES: [{id, frames}] (360, 690, 1350, 750, 600, 750, 450, 450 = 5400) plus the per-recording
                      settings: file, what to record, playbackRate, zoom keyframes
  src/theme.ts        Inter + JetBrains Mono via @remotion/google-fonts; colours from web/app/globals.css dark tokens
                      (--bg #0c0c0f, --ink #f4f4f5, --pass #4ade80, --fail #ff7a6e, greys --g200..g600)
  src/data/bench.ts   each number with a // source: file:line comment
  src/data/captions.ts {scene, from, to, text}; frames are relative to the scene start, so retiming a scene moves its captions
  src/data/links.ts   SITE_URL = "TODO" (one constant), REPO_URL
  src/data/snippets.json  generated
  src/Demo.tsx        <Series> of the scenes, captions overlay, optional <Audio src="vo.mp3">
  src/components/     Recording.tsx (OffthreadVideo/Img or Slate, ▶▶ badge, zoom), Slate.tsx, Captions.tsx
  src/scenes/         Title, Flow, Live, Verdicts, Code, Bench, Limitation, Close (one file each, small)
```
Delete the template's `src/Composition.tsx`.

## Key mechanics
- **Missing files:** `getStaticFiles()` from `remotion` lists `public/`. `Recording` renders the file if it's listed (`.mp4` through `OffthreadVideo`, or `.png` through `Img`). Otherwise it renders `Slate`: dark frame, `RECORDING NEEDED: <file>: <what>`. The same check skips `vo.mp3` when it's absent.
- **Speed badge:** `Recording` applies `playbackRate` from timeline.ts, and the badge prints that same value (`▶▶ 6×`), so the label can't drift from the real speed. No badge at 1×.
- **Zoom:** `interpolate(frame, keyframes, scale/x/y)` on the recording. The keyframes in timeline.ts are placeholders (target the cost line, then the status check) that need tuning once the real recordings exist.
- **snippets.ts:** finds `def decide(` and the first blank line after `return "proven"`, and emits `{file, startLine, lines}`. It also emits the highlight ranges for each precedence step, found by markers inside the snippet (`return "error"`, `"breaks_tests"`, `"doesnt_fix"`, the `unproven` dict, `if blockers or restricted_touched`, `spec_source == "pr_description"`, `return "proven"`). Any marker not found → `console.error` + `process.exit(1)`. A self-check runs it once against the real file. The Code scene dims every line and brightens the active range in turn, with no syntax highlighter.
- **Scene 4:** four cards, each a `Recording` of `rec/03-wrong`, `rec/04-breaks`, `rec/05-inject2` and `rec/06-dep-advisory` (`.mp4` or `.png`). `docs/screenshots/review-wrong.png` and `review-breaks.png` can stand in by copying them to `public/rec/03-wrong.png` and `04-breaks.png`; RECORDING.md gives the `cp` lines. No screenshot exists for inject2 or dep-advisory: `review-inject.png` is the inject PR (Doesn't fix), not inject2, so it must not stand in.
- **Scene 2 diagram:** 8 boxes revealed one by one with `spring`. Model tags come from README.md:81-82: Triage on Nano 3; Localize, Reproduce, Verify-red and Review on Ultra 3. Plain boxes and arrows, nothing that resembles the product UI.
- **Scene 3 captions:** the phase names come from `web/lib/steps.ts`, and the model per phase from the README routing table.

## Also
- `video/RECORDING.md`: one row per rec file: what to show, the target length after cutting (trim dead time only, don't speed up in the editor; Remotion applies the rate), and the badge. Record at 1920×1080 with browser zoom at 125%, and record scene 3 twice.
- `docs/spec/DECISIONS.md`: one 2026-10-29 line on why Remotion (the timeline is code, so code and numbers are pulled from the repo and retiming is one number) and why every product shot is a real recording (no mocked UI in a demo of a tool whose pitch is proof).
- Template extras (`.agents/`, `.claude/skills`, `skills-lock.json`, the template README): add them to video/.gitignore and don't commit them. Replace the README with three lines on how to run it.
- Branch `video` (already checked out). Commit `video/`, the DECISIONS line and this plan, renamed `plans/2026-10-29-demo-video.md`. **No push.**

## Verification
1. `pnpm --dir video snippets` writes snippets.json. Temporarily point it at a copy of review.py with `return "proven"` renamed: it must exit 1 with the marker named.
2. `pnpm --dir video exec tsc --noEmit` passes.
3. `pnpm --dir video exec remotion studio`: Red2FixDemo is 5400 frames, and every recording shows a slate.
4. `pnpm --dir video exec remotion render Red2FixDemo out/red2fix-demo.mp4` renders without errors. Check with `ffprobe`: 180.0 s, 1920×1080, no audio stream when vo.mp3 is absent.
5. Copy one docs screenshot into `public/rec/03-wrong.png` and render a still of scene 4 (`remotion still --frame=…`): the card shows the image, not a slate. Then remove it again.
