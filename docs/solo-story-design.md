# Solo story mode

## Writing method and source

The user requested 20 possible novel-like scenarios and a dedicated solo mode.
The MIT-licensed `novel-writing` package from
https://github.com/wgwtest/novel-writing was downloaded again at commit
`838729695148008d42c01bd7c3c0c1a5c15de830` and compared against the existing
unmodified local package. Its license and source record are retained in
`.agents/skills/novel-writing/`. No duplicate skill installation was needed.
The skill is craft guidance, not a story generator or runtime dependency.
The 20 openings and 120 character profiles are original content authored for
this game, stored in `data/solo_scenarios.json`.

The planning, character introductions, cognition, causality, dialogue, structure,
style, and realism references guided the work:

- **Main task:** turn an unfamiliar location into a bounded social crisis in
  which questioning and collective choices matter.
- **Secondary task:** introduce distinctive people with ordinary interests that
  can explain evasiveness independently of guilt.
- **Point of view:** the human Detective sees the initial scene and public
  character descriptions. Personal accounts are reports, not verified facts.
- **Required characters:** the player and six identifiable, named NPCs, each
  anchored by an occupation, visible trait, prior account, and separate secret.
- **Required information:** the setting, inciting death, criminal interest,
  concrete obstacle to outside help, and why the group must keep evidence safe.
- **Forbidden mistakes:** identifying Mafia through a character's fixed profile;
  leaking one NPC's secrets to another; inventing retrospective clues; repeating
  an opening-night alibi as a newly established later-night fact; releasing all
  private prose to the browser; claiming a small rules system can improvise a
  whole novel.

Openings move from a concrete disruption to discovered stakes and isolation,
then close on a changed social arrangement around an evidence object. Character
entry details distinguish their priorities. Private admissions require pressure
or trust; they do not become automatic role reveals. Factions are dealt after
the briefing independently of names, occupations, and innocent secrets.

## Product flow

1. The initial page has Online play and Solo run choices; public game information
   remains present in the server response for search and no-JavaScript readers.
2. Solo asks for an alias, selects one case, and creates a paused private room.
   The opening and cast are readable without consuming a night timer.
3. Begin starts the Detective plus six bots. Two bots are Mafia, one has the
   Doctor ability, and three are Villagers. A protected first night guarantees
   the player a first conversation. Later nights and timers follow normal rules.
4. Public case information stays in a dossier during the game. Direct questions
   draw from each NPC's own authored account; accusations and defenses still
   use the existing persuasion model.
5. Eliminations and the final account reference the selected case. Replaying
   redeals roles with the same cast and retains room scores. Choosing another
   case or leaving deletes the old solo room and starts fresh.

Online room rules and the ordinary bot dialogue remain available through Online
play. No external LLM or new service is required. Live state is still in memory,
so a server restart ends runs. Browser reload resumes the existing session.

## Knowledge boundaries

`solo_story.public_case` explicitly whitelists public case fields. Secrets and
unspoken alibis are omitted from the browser response. `bot_context` receives
only the current NPC's private profile, public roster/votes, relationship priors,
and role-permitted Mafia teammate information. A secret enters public chat only
when the character actually discloses it; subsequent honesty affects suspicion
slightly and never establishes innocence. Accounts remain stable across rounds.

## Validation

Python tests cover every case, role counts, paused state, privacy before
publication, blocked joining/settings changes, name collision, random selection,
context isolation, disclosures, contextual eliminations, and online compatibility.
Existing game, scoring, phase, bot, and SEO suites also run.

`scripts/check-solo.cjs` checks both mode choices, reading/reloading the briefing,
mobile and desktop overflow, beginning a real Detective turn, a contextual
interview, the final account, another case, and the online lobby. The existing
music, bot chat, phase, and SEO browser checks remain relevant. Browser test
screenshots are local validation artifacts, not shipped game assets.
