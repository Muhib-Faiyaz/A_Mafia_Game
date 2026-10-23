# Narrative implementation and audit

The seven public stories retain their original cast, culprit, Doctor, solution,
and fixed chronology. New structured reasoning annotations support reproducible
complexity ratings. New incident templates carry each setting into night deaths,
rescues, and removals by vote. A separate, unscored practice file teaches a short
evidence route without giving away a public mystery.

## Files and boundaries

Inspected: `solo_story.py`, the seven-case ledger, `death_stories.py`, relevant
`app.py` incident/role routes, `tests/test_solo.py`, `docs/story-catalog.md`, and
`docs/solo-story-design.md`. The narrative changes are in:

- [solo_scenarios.json](../data/solo_scenarios.json): complexity, reasoning notes,
  scene-specific incidents, guarded quiet leads, and one reveal-order correction.
- [tutorial_case.json](../data/tutorial_case.json): a standalone compatible case
  object, `practice-dispatch`; it is not an eighth public catalog selection.
- [case_details.py](../case_details.py): measured public ratings, incident helpers,
  and offline canon validation.
- [test_case_details.py](../tests/test_case_details.py): focused narrative tests.
- [story-complexity.md](story-complexity.md): factors, formula, measured ratings,
  limitations, and reproduction instructions.

The coordinator owns `solo_story.py` integration. The session agent owns the
API route, safe first practice night, and score exclusion. The feature agent owns
the guided UI. The art agent owns image assets and their manifest. No app or
static files were edited by the narrative agent.

## Canon and fair-play review

| Case | Evidence/reasoning audit | Consistency result |
| --- | --- | --- |
| The Ninth Photograph | The repeated bell and fresh reel must be read beside a corridor sighting; the older photograph supplies motive/context without proving the present killing alone. | The two time periods, speaking-tube location check, and limited sightings agree with the fixed timeline. False keeper entries have an explicit clearing comparison. |
| A Room Kept Warm | Empty chair, key return, heat setting, and wheels form a route; neither tracks nor a warm room identify an owner alone. | The key loan, last living sighting, and return interval agree. The inheritance grievance is separated from a later witnessed interval. |
| The Witness in Carriage Six | A stamped delivery is distinct from its owner's location. The whistle discrepancy needs the independent key/empty-seat route. | Boarding, last living sighting, access, and return fit the train chronology. A forged warning date does not substitute for a missing journey. |
| What the River Returned | Bay orientation and an independent drain plan identify the survey error; a sheet count needs the backing impression to establish content. | The opening, argument, open-tube departure, and missing fold fit the chronology. Compliance with notices is distinguished from the underlying survey fraud. |
| The Last Dress Rehearsal | Recorded cues, listening position, manually removed pin, and gallery sightings form separate checks. | The blackout/hold/work-light sequence agrees with the fixed reconstruction. The irregular repair and false wage invoice have explanations separate from the criminal payment trail. |
| The Winter Seed | An arrival signature does not cover an interval; copied label continuity does not establish packet or seed identity. | Last living sighting, signed replacement, and exit sighting align. Fuel theft has a resolving comparison and is not treated as proof of the sample substitution. |
| The Quiet Sentence | Key/portfolio route and private-wording disclosure support each other. Hearing an objection is distinct from knowing the exact final wording. | Private interview, muted link, printing, and return agree. The translator's earlier error is separated from access during the private interval. Chapter one now preserves the sealed page. |

No additional structural contradiction was found in this review. These are
authored mysteries with fixed retrospective reconstructions; automated checks
validate the ledger, not forensic certainty or every possible alternative a
reader might imagine. The endings preserve the existing interpretation and do
not alter NPC voting rules.

### Findings and revisions

- **Location:** `quiet-sentence`, first chapter. **Problem type:** cognition and
  disclosure / reveal timing. **What happened:** the chapter put the old sentence
  beside the new one before the player inspected the sealed correction.
  **Why it failed:** scene staging implied an exhibit had already been opened.
  **Revision direction:** keep the clean correction sealed until inspection and
  distinguish objection, wording, and disclosure time. **Project rule:** yes;
  chapter narration must respect the same exhibit gates as the journal.
- **Location:** the common solo night/vote/rescue messages. **Problem type:**
  scene anchoring and knowledge boundaries. **What happened:** generic text
  repeated across all settings; rescues supplied little case texture.
  **Why it failed:** incidents felt detached from the current inquiry and did
  not reinforce careful evidence use. **Revision direction:** use public scene
  props and the concrete cost of losing a witness; add a quiet procedural lead
  only after all supporting clues are public. **Project rule:** yes; an incident
  may remind the reader of evidence, but cannot discover it on an NPC's behalf.

## Incident contract and stage limits

`death_story(room, name, cause)` and `rescue_story(room, name)` read a case's
`incidents` object. `night`, `vote`, and `rescue` are local base templates with a
single allowed `{name}` field. Vote removals retain the established guard/
withdrawal framing. Rescues never identify the Doctor or claim who acted.

Optional `leads` declare a cause, minimum round, and required clue IDs. Every
source must exist in the case and in `room['story']['revealed']`; first-watch
text therefore cannot borrow a later discovery. Leads are narrator reminders,
never an NPC's newly composed accusation, a new journal clue, a cause-of-death
diagnosis, or an extra voting weight. Helpers do not mutate state.

Public props agreed with the art agent: chart table/reel/photo; hospice dining
room/old-wing heat; carriage lamps/deposition; archive drying frames/numbered
door; theatre work lights/bell; preparation bench/reference; protection-house
front-room table/statement. No new weapon, culprit-specific portrait, or visual
identity clue was requested. Text avoids invented last words or conveniently
discovered private admissions. Existing sealed pre-watch observations remain
available through the original evidence system; unwritten answers do not.

## Practice handoff

The Missing Practice Dispatch is explicitly an announced simulation at a
volunteer hall. Nobody is killed or injured. Six NPC profiles use the normal
account/observation/admission/correction schema, with a fixed saboteur and Doctor,
clues, connections, timeline, reconstruction, chapters, and endings.

The guide uses the actual engine:

1. Read the six accounts. The first automatic observation belongs to Theo.
2. Ask **Mara** the **detail** question (`mara-observation`); it is still new.
3. Inspect the first exhibit, `dispatch-log`.
4. These sources plus `ellis-account` unlock `dispatch-route` automatically.
   The Compare action can then truthfully say all supported comparisons are
   already recorded; there is no hidden extra click needed to activate evidence.
5. Ask the group to **Suspect Ellis**. The comparison contributes 2.2 suspicion;
   the shared team position contributes 1.6. That exceeds the existing 2.5 NPC
   voting threshold. Influence does not itself cast a ballot.
6. Proceed to voting and vote for **Ellis**. With the cast available, the normal
   evidence-driven NPC ballots support the same target in this first round.

Case ID: `practice-dispatch`. Stable cast keys: `mara`, `ellis`, `june` (Doctor).
Public display names may be renamed on collision with a player's alias; the
coordinator/session guide must resolve runtime target IDs from these keys.
Night investigation can target any witness; the exercise's evidence path does
not require a successful night check. The API/session agent enforces the safe
first night and no-score behavior; these are not achieved by the JSON alone.

## Skill assessment and provenance

Independently inspected available skills and existing project tooling. Existing
installed writing packages materially help this work; additional installation
would duplicate them. No install, download, credential access, upstream code
execution, or external text-generation service was needed.

- [novel-writing](../.agents/skills/novel-writing/SKILL.md),
  [source record](../.agents/skills/novel-writing/SOURCE.md):
  `https://github.com/wgwtest/novel-writing`, revision
  `838729695148008d42c01bd7c3c0c1a5c15de830`, MIT. Applied
  `cognition-layers-and-language`, `scene-causality-and-agency`, and
  `revision-checklist` to private/public knowledge, witness limits, and reveal order.
- [Story Skills genre-craft](../.agents/skills/story-skills/genre-craft/SKILL.md)
  and [scene-craft](../.agents/skills/story-skills/scene-craft/SKILL.md),
  [source record](../.agents/skills/story-skills/SOURCE.md):
  `https://github.com/danjdewhurst/story-skills`, revision
  `57121ee512c6d4218a285c6991193347944f31b0`, MIT. Applied
  `mystery-fair-play`, `openings`, and `dialogue-subtext` to the clue ledger,
  resolved distractions, the practice premise, and limited witness answers.
- Managed-cloud runtime skill `c0/cloud-environment-runtime` was read and
  `cloud_environment.environment_status` checked at startup. No network work
  followed; readiness was not assumed from an unknown policy state.

Discovery/read commands used `rg --files`/`find .agents` for existing packages
and `cat` for their `SKILL.md`, `SOURCE.md`, and named references. Installation
commands: **none**. Existing pinned source records serve as the trusted source
search; no duplicate registry download was necessary. This is a JSON game-canon
project, not a Story CLI manuscript project, so ledger/source/reveal checks use
the existing Python schema instead of adding manuscript scaffolding.

## Focused validation

`python -m unittest discover -s tests -p 'test_case_details.py' -v`:
**10 tests passed**. Coverage includes all eight stored objects (seven public,
one practice), all five rating thresholds, stale/private metadata rejection,
local incident templates, every partial/missing lead gate, stage limits, helper
purity, the sealed correction, and the real story engine's first-round practice
question → exhibit → comparison → influence → NPC ballot path.

The narrative agent did not run a duplicate full suite. API/session integration,
browser tutorial behavior, responsive visuals, and complete game flows belong
to the coordinator's integrated verification; the focused engine test does not
claim those checks passed.
