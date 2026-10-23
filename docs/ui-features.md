# Gameplay and UI implementation

The UI reuses the Flask JSON endpoints and existing vanilla JavaScript renderer, morphdom updates, dialogs, typography, and night atmosphere. No frontend framework or runtime dependency was added.

## Practice

Choose **Solo run → Practice tutorial** before entering a live case. The server creates an independent `tutorial=true` solo room; the UI does not replace a live room with practice. The tutorial uses the actual night turns, confirmed Detective investigation, one-question quota, scene evidence, supported comparisons, influence model, and final ballot. The practice room awards no session points and is excluded from the seven-story catalog.

The guide observes `phase`, `night_step`, `pick`, `scenario.interrogation`, revisions, journal documents, connections, and the server influence result. It recommends investigating Ellis, asking Mara “What detail did you leave out?”, inspecting the dispatch log, comparing the sources, Suspecting Ellis, and confirming the final ballot. `scenario.tutorial_guidance` supplies runtime witness IDs, so an alias that renames a witness does not break guidance. Players retain normal choices; skipped steps are not falsely reported as completed. A rejected request remains visible until the next stance or round.

## Five screens

| Lower tab | Content and controls |
| --- | --- |
| Round | Phase progression, private findings, living roster, night investigation, one selected question, final ballot |
| Case journal | Recorded accounts, statement revisions, collected evidence, inspections and comparisons |
| Dossier | Story setting, complexity, opening, cast, chapters, ending, reconstruction and solution |
| Influence | Suspect, Defend, Withdraw, voting guidance and persistent server result |
| Chat | Public witness accounts and private Detective team chat/invitations |

Only the selected panel is visible. Tabs expose their selected state, control a named panel, and support Left/Right/Home/End with one tab stop. Five equal columns fit a 320px viewport. Gold highlights, dark surfaces, the existing display face, visible focus outlines, 48px controls, and restrained static feedback preserve the established visual identity. The original landing markup was left unchanged to preserve its server/client HTML contract.

The story selector, complete story list, briefing, and Dossier render the data-provided five-star complexity plus an accessible numeric label and explanation. Background URLs are restricted to the shipped turn or case directories. At 700px and below CSS selects `turn_background_mobile`; larger screens select `turn_background`. Both use `cover`, preserving aspect ratio and allowing the art agent's separate compositions.

Coordinator integration also updated `static/horror.css`: its later overlay rule
must select the same portrait variable at phone widths. The final artwork
browser check verifies the computed image for every live phase.

## Influence feedback

`POST /api/solo-influence` returns `influence.status`, `message`, target name, before/after intention targets and `changed_witnesses`. During the request, controls are disabled and the panel exposes `aria-busy=true`. The persistent polite status region distinguishes:

- Submitting: no server result yet.
- Accepted: the stance was stored, with the real changed-witness count and names; zero changes is explicitly reported.
- Already recorded: an unchanged stance caused no new action.
- Rejected: the actual server error remains visible across polling.

The UI describes changed **current intentions** and explains that later evidence can change the final vote. Suspect, Defend, and Withdraw do not submit the team's ballot. Influence closes when voting opens. The latest accepted server result is restored from `scenario.influence_feedback`; a local per-room/player/round record also preserves feedback over reload.

## Teammate notifications

Private Detective and Mafia messages use each channel's monotonic `seq`. Read/seen cursors are stored in localStorage by `(code,pid)`; Mafia cursors additionally follow the round because their sequence resets on restart. The first snapshot establishes a baseline, so historical messages do not replay notifications. A reload restores unread counts without replaying toasts. Own messages use `speaker` identity and system messages are excluded.

New offscreen messages update the Chat badge and its accessible name, and use the existing polite live-region toast with a short message preview. They do not open a modal or switch screens. Reading requires the actual message panel to intersect the visible viewport, with its tab visible and private details expanded, while the document is visible. Merely polling, changing the friend count, or leaving a panel collapsed does not mark it read.

## Next story

After a case, **Choose another story** opens `#next-case-picker`. Confirmation calls `POST /api/solo-next` with `scenario_id`; it never calls Leave. The room code, session/player identity, invited friends, invite token and private chat remain, while the team sees the next briefing. Explicit Leave and Close case still use the existing leave behavior.

## Validation

- `node --check static/game.js` — passed.
- `node --check scripts/check-gameplay-features.cjs` — passed.
- `node scripts/check-gameplay-features.cjs http://127.0.0.1:5050` — passed against the integrated Gunicorn server and `/usr/bin/chromium`.
- `git diff --check` — passed for the integrated worktree at verification time.

The new browser check performs real practice progression through a town win and zero score; pending/accepted-zero/accepted-with-changes/unchanged/rejected influence; rejection persistence through polling; accepted-result persistence through reload; distinct tab contents; all five panels at 320/390/1440px without horizontal overflow; keyboard selection and focus; private-message deduplication, own-message suppression, persisted unread state, read-on-visible-panel behavior, polite live region and no stale reload toast; and next-story continuity for the lead, friend, and private chat. Chat sends retry only the real server's short rate-limit rejection, with a bounded retry count.

Visual captures are written to `/tmp/mafia-features-journal-320.png`, `/tmp/mafia-features-influence-320.png`, `/tmp/mafia-features-round-390.png`, `/tmp/mafia-features-influence-1440.png`, and `/tmp/mafia-features-chat-unread-390.png`. The mobile Journal and Influence, desktop Influence, and mobile unread-notification captures were visually inspected. Automated viewport/keyboard checks are not a full accessibility conformance audit; axe and Lighthouse are not installed in the current Node toolchain.

## Skill assessment and sources

Inspected the existing `.agents/skills` catalog and pinned source records independently. Reused [frontend-design](../.agents/skills/frontend-design/SKILL.md) from [Anthropic skills](https://github.com/anthropics/skills) at `dbd4588f9e1033efb41dad4bef2f7947c8993d44` and [accessibility](../.agents/skills/accessibility/SKILL.md) from [Addy Osmani web-quality-skills](https://github.com/addyosmani/web-quality-skills) at `afa8da942115f2961fdbfa80807ea0b232ff6c00`. Reviewed their instructions, license/source files, dependencies and permissions before use. They require no executing installation scripts, credentials or external services. The core-web-vitals guidance was assessed; no unrelated metric optimization was added without evidence. The managed cloud runtime skill and environment status were also read as required.

No skill installation or download was needed, so there are no installation commands. Existing Playwright and Chromium supplied browser coverage. New UI code is limited to `static/game.js`, `static/game.css`, this report and `scripts/check-gameplay-features.cjs`; backend/session/story/art changes are owned and tested by their respective agents/coordinator.
