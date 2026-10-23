# Mafia: After Dark — implementation report

## My original to-do list

**IMPORTANT: Preserve the following to-do list exactly as written. Do not rewrite, correct, shorten, or change my wording.** You may add technical implementation plans underneath each item, but keep the original text unchanged.

- Fixing auto kick out of friends in solo run…and also check does it eliminate playing session the game is ended…I think it does
- Have a small tutorial round..teach what to do…with what actions to choose what things to be careful of..how influence vote..

- Have a complexity meter of stories…5 stars system
- Make different art  back grounds for both mobile and pc…that matches the story….voting will represent a part of the room,,doctor will show another, detective will show another and so on…
  &#x20;the mafia killing message should carry story elements…and also should give quiet hints
- Give feedback when using the influence the group..because I don’t know weather it worked or not.
- Have case journal open a  total different window like the dossier and chat…have the influence section separate in the lower tab and do the same for this to
- When there is a new chat from a teammate there should be a notification

## Execution plan

1. Reproduce session and reconnection behavior before changing it.
2. Implement tutorial, feedback, dedicated screens and teammate unread notifications.
3. Add stored complexity ratings and story-aware incidents with fair, subtle hints.
4. Establish a visual guide and representative art, then complete responsive story scene assets.
5. Integrate, run server and browser regressions, and record exact results below.

## Shared interfaces and file ownership

- Session agent: `app.py`, lifecycle tests; preserve current room and teammate sessions when replaying or choosing another case. Frontend session changes go through UI agent.
- UI agent: `static/game.js`, `static/game.css`, new UI browser checks. Tabs: `round`, `journal`, `dossier`, `influence`, `chat`.
- Narrative agent: case JSON, tutorial JSON, `case_details.py`, narrative tests and rating/skill notes.
- Art agent: `static/images/cases/`, asset manifest and visual guide. Scenes: `mafia`, `doctor`, `detective`, `discussion`, `voting`; separate desktop and mobile variants.
- Coordinator: `solo_story.py`, `case_art.py`, integration, documentation and final checks.

## Results

The original list above is preserved verbatim. The numbers below follow its
original order and provide the implementation checklist without rewriting it.

| Item | Status | Result |
| --- | --- | --- |
| 1 | Completed | Reproduced story selection deleting the room; normal endings were already safe. Next story now retains room, lead/friend identities, invitation, private chat, and Detective score. |
| 2 | Completed | A separate, unscored practice case guides actual investigation, one selected question, exhibits, comparisons, persuasion and a final ballot. Its first night is safe. |
| 3 | Completed | Five-star complexity in picker/list/briefing/Dossier, measured from the clue ledger and reviewable reasoning annotations. |
| 4 | Completed | Case-local death/rescue/vote messages and public-evidence-gated quiet leads; 70 distinct WebPs cover seven stories, five scene locations, and both mobile and desktop orientations. |
| 5 | Completed | Submitting, accepted, unchanged and rejected feedback; actual before/after witness preferences, named changes, honest zero-effect responses and reload persistence. |
| 6 | Completed | Separate Round, Case journal, Dossier, Influence and Chat screens; five accessible lower tabs with keyboard navigation. |
| 7 | Completed | Private teammate unread badge and polite toast; sequence deduplication, sender identity, persistent read state and visible-panel read handling. |

## Major files and decisions

- `app.py`: same-room `/api/solo-next`, practice creation and score exclusion,
  safe first practice night, message sender IDs, influence response, story
  rescues, and responsive art state. No new framework or runtime service.
- `solo_story.py`: safe public complexity and practice guidance, real influence
  outcomes and persistence, phase gating, and story incident integration.
- `case_details.py`, `data/solo_scenarios.json`, `data/tutorial_case.json`:
  measured ratings, canon checks, local incidents and a standalone practice
  file. Corrected the Quiet Sentence chapter's prematurely opened exhibit;
  existing culprits, roles and solutions remain intact.
- `static/game.js`, `static/game.css`, `static/horror.css`: dedicated screens, guided practice,
  accessible tab controls, feedback, notifications, story picker continuity,
  and responsive image selection.
- `case_art.py`, `static/images/cases/`: manifest-driven scene art with existing
  artwork as fallback for online play and practice.
- New lifecycle, influence, narrative and asset tests; a new gameplay browser
  check and a responsive artwork check. Existing solo browser checks now use
  the separate screens and assert same-room story selection.

Detailed findings: [sessions](session-findings.md),
[UI](ui-features.md), [narrative](narrative-report.md),
[complexity](story-complexity.md), [visual direction](visual-guide.md),
[art delivery and sources](art-report.md).

## Verification

Testing is performed with the existing Python virtual environment, Flask test
client, single-worker Gunicorn, Playwright, and Chromium. There is no frontend
build step; the project serves plain HTML, CSS and JavaScript directly.

- **155 server tests passed** using
  `PYTHONDONTWRITEBYTECODE=1 /workspace/.venvs/a-mafia-game/bin/python -m unittest discover -s tests -q`.
  This includes all shipped art paths, a complete one-round practice victory, no-score
  settlement, preserved friends across endings/replay/new stories, online
  lifecycle, private scoring, bot pacing, hidden knowledge, questions and votes.
- `node --check static/game.js` and `node tests/test_music.cjs` passed.
- Browser checks passed: `check-phase-flow.cjs`, `check-bot-chat.cjs`,
  `check-solo.cjs`, `check-solo-team.cjs`, `check-solo-journal.cjs`,
  `check-seo.cjs`, `check-gameplay-features.cjs`, and `check-case-art.cjs`.
- The new gameplay browser flow checks real practice actions and a town win,
  truthful pending/accepted/zero-effect/unchanged/rejected feedback, reload,
  keyboard controls, all five screens at 320/390/1440px, teammate alerts and
  same-room next-story continuity. It does not substitute mocked game state.
- All 70 images decode in Chromium at their expected dimensions. Live Mafia,
  Doctor, Detective, discussion and voting phases select the correct device
  variant at 320/390/1440px with no horizontal overflow.
- Coordinator visually reviewed phone Journal, Round, Influence and unread
  notification captures, desktop Influence and voting, portrait Detective art,
  the initial desktop/mobile source set, and hospice, seed-repository and train
  sources. The art specialist reviewed all 21 sources and all 70 delivery crops.
- Delivered art totals 7,451,692 bytes (7.11 MiB), plus 21 compact source sheets
  for review and reframing. Asset hashes, dimensions and crop regions are
  recorded in `static/images/cases/asset-catalog.json`.

Failures found during implementation were resolved: the initial test run
preceded creation of the practice JSON; an old browser script submitted an
empty required alias after reload; an agent browser test initially read score
from the wrong public field; and a deliberate server reload interrupted an
early browser run. A review also caught rejected influence feedback being
overwritten by polling and an unread count hidden from assistive technology;
both were corrected and covered by the browser check. No final result is
left failing. The first art browser run also caught the older `horror.css`
overlay overriding mobile image selection; its responsive rule now uses the
portrait variant, and the complete art browser check passes.

## Skills and dependencies

Each specialist independently assessed the supported skill registry, existing
packages and project tooling. No new skill or package installation was needed;
installation commands: **none**. Existing pinned sources were reused:

- `novel-writing`: [wgwtest/novel-writing](https://github.com/wgwtest/novel-writing),
  revision `838729695148008d42c01bd7c3c0c1a5c15de830`; scene causality,
  knowledge boundaries and revision checks.
- `genre-craft` and `scene-craft`:
  [danjdewhurst/story-skills](https://github.com/danjdewhurst/story-skills),
  revision `57121ee512c6d4218a285c6991193347944f31b0`; fair clues, scene
  continuity and limited witness knowledge.
- `frontend-design`: [anthropics/skills](https://github.com/anthropics/skills),
  revision `dbd4588f9e1033efb41dad4bef2f7947c8993d44`; existing visual identity.
- `accessibility`:
  [addyosmani/web-quality-skills](https://github.com/addyosmani/web-quality-skills),
  revision `afa8da942115f2961fdbfa80807ea0b232ff6c00`; tab keyboard/focus,
  readable feedback and non-disruptive notifications.
- Managed cloud runtime skill and environment/network inspection; existing
  `unittest`, Playwright and Chromium. The art specialist found no useful
  additional install and uses the available image-generation tool.

The specialist reports record their source files and assessment commands. No
untrusted install scripts, new AI runtime API or credentials were added.

## Known limits and remaining manual steps

- Rooms remain in memory. A server restart clears them; six hours without any
  room requests makes a room eligible for the existing cleanup. Explicit lead
  Leave closes a solo room. Case completion and next-story selection keep it.
- Complexity measures authored deduction demands, not measured player win
  rates. A lucky private investigation can still identify the culprit.
- Desktop art uses landscape crops; mobile uses portrait adaptations. Some
  desktop regions are enlarged from source sheets. They suit background use
  rather than close-up print inspection; the visual guide documents dimensions.
- Automated Chromium checks cover representative widths and keyboard behavior,
  not every browser/device or a full accessibility audit.
- After deployment, run the practice once on a real phone and PC. Invite a
  second device, send a private message while its Chat is hidden, open/read it,
  end the case, choose another story, and verify both identities remain.
  Deployment itself is outside this change; local tests do not claim a live
  service was updated.
