# Mobile performance work

Installed and applied Addy Osmani's MIT-licensed `performance` and
`core-web-vitals` skills, pinned to
`afa8da942115f2961fdbfa80807ea0b232ff6c00`. Their full instructions,
references, license and provenance live in `.agents/skills/`.

## Evidence

Baseline: `b1c49b3`. Local Chromium 154.0.8037.57 with Playwright 1.62.1, 390×844 mobile viewport,
4× CPU slowdown, 1.6 Mbps down / 750 Kbps up, 150 ms latency, cache disabled.
Each navigation number is the median of three cold runs. Resources are from
`PerformanceResourceTiming`; the body-byte total excludes the HTML document.
This is lab evidence, not production INP or real-user Core Web Vitals.
There is no supplied production URL or field dataset; localhost has no CrUX.

| Signal | Before | After |
| --- | ---: | ---: |
| Initial subresource body bytes | 2,345,590 B | 205,449 B |
| Opening artwork complete | 12.43 s | 1.82 s |
| Network idle / completed load observation | 13.04 s | 2.38 s |
| First contentful paint | 1.032 s | 0.792 s |
| Largest contentful paint | 1.300 s | 1.144 s |
| Cumulative layout shift | 0 | 0 |
| Role handler, median of 10 | 80.4 ms | 2.6 ms |
| Player selection handler, median of 10 | 58.0 ms | 1.6 ms |
| Chat input retained across those 20 interactions | 0/20 | 20/20 |

Navigation ranges: FCP 0.856–1.076 s before vs 0.764–0.868 s after;
LCP 1.088–1.340 s before vs 1.076–1.200 s after; completed load observation
12.89–13.07 s before vs 2.36–2.39 s after. LCP is the prominent text here;
it does not capture the later completion of the decorative background.
Network-idle observations include the tool's wait, so they are not TTI.
Timings vary with machine load. Transfer sizes and retained DOM identities
provide stronger evidence than small paint-time differences.

The interaction trace uses a 20-player Mafia night and 10 role reveals plus
10 selections at 4× CPU slowdown. The median time to two following animation
frames fell from 133.3 to 49.5 ms for role reveals and from 100.6 to 33.5 ms
for selections. These synthetic samples are not field INP. CDP trace files
were captured as `/tmp/mafia-trace-baseline.json` and
`/tmp/mafia-trace-optimized.json`; compact raw observations are committed in
`performance-results/`.

## Changes tied to the measurements

- Serve WebP artwork: opening PNGs fell from 2.2 MB each to 148–162 KB.
  Turn/death backgrounds are encoded for 960px width, all under 250 KB.
  Keep originals for regeneration and existing client URLs; prefer one
  representation per scene so encoding variants do not duplicate the pool.
- Update role and selection controls directly. Reconcile server updates with
  locally vendored morphdom 2.7.8 (5.3 KB minified / 2.2 KB gzip), skipping
  identical elements and preserving active inputs, caret/IME state, focus,
  chat scroll and the lobby guest-list scroll position.
- Return the caller's authorized state with successful requested mutations,
  removing a second request/response cycle. Legacy API clients still work.
  Ignore in-flight snapshots from before an action or session change.
- Stop hidden-tab polling, resume immediately on visibility, and only write
  changed timer text. Progress uses transform instead of changing layout width.
- Gzip text/JSON with Flask-Compress. Revalidate HTML, scripts and styles with
  correct gzip ETags; cache static artwork/audio/fonts for one day. Game API
  responses use `no-store`.
- Bound the decoded soundtrack cache to two tracks. The five MP3s represent
  roughly 140 MB of stereo float audio at 44.1 kHz. The tested discussion/vote
  cache held 63,046,200 bytes rather than all five tracks; crossfades still work.
  Earlier tracks can be supplied by the browser HTTP cache and decoded again.

## Validation and reproduction

36 Python tests pass, including compression/revalidation, API privacy and
compatibility, action-state responses, all gameplay/scoring tests and the
unique optimized image pool. Browser checks cover stale-poll races, focused
chat inputs, caret ranges, composition text, chat send, local action feedback,
scroll retention, hidden-tab polling, all five music tracks, anonymous rescue
notices, scoring/restart, opening/tutorial flows and 320/390/430px layouts.
No gameplay timing or scoring rules changed.

Run the application with the updated `requirements.txt` in a single worker.
The optional browser scripts use Node, Playwright and `/usr/bin/chromium`:

```sh
python -m unittest discover -s tests -q
node scripts/check-responsiveness.cjs
node scripts/trace-interactions.cjs review
node scripts/measure-performance.cjs review
```

The last two save lab observations and a CDP trace to `/tmp`. These scripts
create test rooms on the local server. To regenerate WebP copies from the
retained originals, install FFmpeg with libwebp and run
`scripts/optimize_art.sh`; FFmpeg is not needed by the running game.
