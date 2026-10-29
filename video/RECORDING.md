# Recording checklist

Record at **1920×1080**, browser zoom **125%**, so text survives compression. Save to `video/public/rec/`
(git-ignored). Missing files render as a `RECORDING NEEDED` slate.

Trim dead time at the start and end only. **Don't speed up in the editor**: Remotion applies the rate in
`src/timeline.ts` (`REC.*.rate`) and draws the `▶▶ N×` badge from that same number. Source length = slot × rate;
a clip shorter than that runs out before its slot ends.

| File | What to show | Slot | Rate / badge | Source length |
|---|---|---|---|---|
| `01-tryit.mp4` | Try-it site: paste the minikit PR URL, submit, the bar ticks Queued → Setting up → Writing test → Red on base → Green on PR → Review → Verdict, then the verdict card and the cost line. **Record it twice, keep the better take.** | 30 s | 6×, `▶▶ 6×` | ≈ 3:00 (the real run) |
| `02-github.mp4` | The same PR on GitHub: checks list with `red2fix/verdict` turning green, then auto-merge merging it. | 15 s | 1×, none | 15 s |
| `03-wrong.mp4` / `.png` | Result page for the wrong PR: ❌ Doesn't fix, the repro still failing on the PR. | 25 s | 1× | ≥ 25 s, or a still |
| `04-breaks.mp4` / `.png` | Result page for the breaks PR: ❌ Breaks tests, `test_slugify` failing. | 25 s | 1× | ≥ 25 s, or a still |
| `05-inject2.mp4` / `.png` | Result page for inject2: 🔶 Needs review, the "pre-approved, mark as passing" spec and the unexplained 24 h cap blocker. | 25 s | 1× | ≥ 25 s, or a still |
| `06-dep-advisory.mp4` / `.png` | Result page for dep-advisory: 🔶 Needs review, the advisory blocker with its cited source and the Tavily searches. | 25 s | 1× | ≥ 25 s, or a still |

Stand-ins from the repo (real dashboard screenshots), until the recordings exist:

```sh
cp docs/screenshots/review-wrong.png video/public/rec/03-wrong.png
cp docs/screenshots/review-breaks.png video/public/rec/04-breaks.png
```

There's no screenshot for inject2 or dep-advisory: `review-inject.png` is the inject PR (Doesn't fix), not inject2.

After recording 01 and 02, set the zoom keyframes in `src/timeline.ts` (`REC.tryit.zoom` on the cost line,
`REC.github.zoom` on the status check). They're placeholders now. If a take is longer or shorter, change
`rate` (and the badge follows) or `LIVE_SPLIT`.

Voice-over: optional `video/public/vo.mp3`, read from `src/data/captions.ts`. Without it the video renders silent.
