# Seven solo mysteries

Solo mode has seven original thriller cases, each with six witnesses, one fixed
Mafia culprit, a Doctor, and the human Detective seat. The case timeline and
solution are authored together. Replaying a case preserves its culprit; a new
case offers a new mystery. Online rooms retain their configurable roles and
social-deduction dialogue.

## Writing skill and craft

The MIT-licensed [novel-writing skill](../.agents/skills/novel-writing/SKILL.md)
was downloaded from https://github.com/wgwtest/novel-writing at the current
upstream commit `838729695148008d42c01bd7c3c0c1a5c15de830` and verified against
the installed package. License and provenance remain alongside the skill.
Its planning, cognition, dialogue, character introduction, causality, structure,
realism, and revision references guided this rewrite. The prose is original;
it does not reproduce or claim to imitate a particular novelist.

The narrative task is to make an account change the reader's next question.
The secondary task is to distinguish moral failure from the murder itself.
The player's viewpoint is limited to introductions, spoken testimony, inspected
exhibits, and their private Detective findings. Each witness has a stable role,
relationship, account, observation, private shame, and defensive response.
Author-only fields contain the culprit, chronology, comparisons, and solution.

Required information: an identifiable victim, a reason for the meeting, an
obstacle to outside help, the criminal interest at stake, and independent ways
to test the culprit's account. Forbidden shortcuts: automatic villain
confessions, evidence that changes to fit randomized roles, invented facts in
answer to unsupported prompts, identical alibis at each dawn, ghost dialogue,
and a definitive accusation based on one ambiguous observation.

## The cases

| Case | Central question | Sources that can be compared |
| --- | --- | --- |
| The Ninth Bell | Why does an old distress call contain tonight's sound? | Bell timing, roof access, a speaking tube, reel stock |
| A Room Kept Warm | Why is an empty hospice room heated during an evacuation? | A borrowed key, an empty chair, luggage tracks, an altered transfer |
| The Witness in Carriage Six | Can a stamped receipt establish an alibi? | Departure signal, porter records, a spare key, a missing journey |
| What the River Returned | Which building was actually surveyed? | A displaced door, drain plans, a missing fold, a surviving impression |
| The Last Dress Rehearsal | Who could have heard a cue that was never called? | A disconnected monitor, rehearsal audio, a gallery route, a brake pin |
| The Winter Seed | Is a continuous label proof of a continuous sample? | Envelope stock, a duplicate label, arrival records, an omitted handover |
| The House Below the Tide | When did a shared memory become a manufactured account? | Original notes, adjacent photographs, a hire carbon, a repeated omitted journey |

Each case has two independent chains that challenge its culprit, plus a
comparison that separates an innocent person's wrongdoing from the central
crime. Comparisons require every supporting item to have been published. The
culprit answers with an authored qualification or deflection, not a confession.
The initial murder chronology never changes as later watches and votes occur.

## Runtime conversation and consequences

`solo_story.discussion` is a separate solo conversation engine. It uses no
online dialogue templates. `bot_brain.read_message` is shared only as a parser
for names, accusations, defenses, and direct address.

- Initial accounts appear once, paced over time. At most two unsolicited
  observations appear per day. Repeated polls or new days do not replay them.
- Direct questions can publish an account or an observation. A first request
  for a secret receives that character's defensive response. Trust or renewed
  pressure can produce the private admission once.
- Natural questions about case topics can elicit relevant observations.
  Inspecting the scene reveals one authored exhibit at a time.
- Published combinations trigger a witness's comparison and the subject's
  response. Every line and comparison is remembered for the entire run.
- Unsupported or exhausted questions return a private interface hint. They do
  not create a fictitious answer or recycle an accusation.
- Characters under guard or dead stop speaking. Their signed pre-watch accounts
  and observations can be read as archived material. Unspoken personal
  admissions cannot conveniently be recovered from their notes.

Ballots use only public comparisons and the Detective team's explicit claims.
One unsupported accusation cannot force a chorus of votes; one partial
comparison plus a player's argument can change the outcome. Two corroborating
comparisons carry more weight than a single defense. Repeated claims replace
rather than accumulate. Hidden roles and the private solution are not inputs to
these beliefs. Private Detective and team-chat findings are never fed into them.

The Mafia's later target selection reacts to witnesses who publicly supply
information and corroboration. The Doctor can protect an exposed witness based
on the same public record. Publishing evidence therefore changes both the
argument and the next watch's risk. Outcomes include case-specific endings,
the absent witnesses, the evidence preserved, and the comparisons made. A
completed game also exposes the fixed solution and chronology for review.

## Interface and existing rules

The briefing is untimed. During play, the case dossier retains the opening and
cast. The case journal offers account, observation, and private-question buttons,
scene inspection, comparisons, and a durable record beyond the chat buffer.
The lead can also type questions in town chat. Friends share the journal but
continue discussing privately and acting through the same Detective seat.

Solo has exactly one Mafia, one Doctor, four Villagers, and the Detective.
The two-friend cap, one shared ballot, one investigation, shared scoring, and
lead-only game controls remain. Normal timers apply. The Detective is protected
from vote-outs and ordinary night attacks. On a final-chance night (two town
members and one Mafia left), a Detective who has not identified the living Mafia
can be killed; a correct finding before dawn restores protection. Doctor rescues
still apply. Removing the sole Mafia ends the case immediately in a town win.

Live state remains in memory. Reloads resume the session; a server restart ends
it. No external text-generation service or API key is required. These are authored
interactive mysteries with bounded language handling.

## Validation and editorial checks

Tests cover all seven cases, source references, independent clue chains, hidden
content, fixed-role replay, aliases, finite dialogue, pressure and trust, archived
accounts, evidence-dependent ballots, public-information boundaries, and target
selection. Team, final-night, online game, scoring, and phase tests remain in place.
`scripts/check-solo-journal.cjs` completes an inquiry through public chat and
ballots. Browser checks cover the journal controls, evidence persistence, truthful mode
copy, mobile layout, shared sessions, and existing online flows.

The prose review checks access and timing in each case: a sound cannot establish
a face; a signature can establish arrival without duration; a label cannot
establish contents; an old wrongdoing cannot establish the present murder.
Endings distinguish a solved case from a lost one. Post-verdict explanations
state hidden history without implying evidence was recovered in a Mafia victory.
