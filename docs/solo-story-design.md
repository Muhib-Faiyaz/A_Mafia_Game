# Seven solo mysteries

Solo mode has seven original thriller cases, each with six witnesses, one fixed
Mafia culprit, a Doctor, and the human Detective seat. The case timeline and
solution are authored together. The selector supports an explicit title or Random, with source labels.
Replaying a case preserves its culprit; a new case offers a new mystery. Online rooms retain their configurable roles and
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
answer to unsupported prompts, repeated account spam within a round, ghost dialogue,
and a definitive accusation based on one ambiguous observation.

## The cases and sources

The [public catalog](story-catalog.md) records every title and source. Five
original novel-writing cases remain, The Ninth Photograph combines two earlier
novel-writing cases, and The Quiet Sentence is new work applying the downloaded
Story Skills genre-craft and scene-craft references. Both skill packages remain
installed alongside novel-writing. Every case has explicit reconstruction prose
covering means, opportunity, motive, and the other characters' relevant actions.

## Manual rounds, statements, and decisions

`solo_story.discussion` runs once when a gathering begins. It publishes one
current account per living witness and archives pre-watch material from missing
witnesses. A per-round ledger prevents repeated polling from issuing accounts
again. One fresh pre-watch observation joins the round's account without a
second speech. No clock or background polling advances a solo phase.

The Detective team shares a one-question allowance for the round. A selected
living witness can be asked for a missing detail, hidden motive, or correction.
Answers come from that person's authored observation, admission, or correction;
the before/after statement is retained. The quota and revision are updated under
the room lock, so simultaneous friend requests cannot create two questions.
An already recorded answer cannot be asked again. Starting the next round makes
one new question available. There is no free-text public-question parser.

Scene inspection and comparisons are separate actions. Public exhibits remain
available; sealed observations of inactive witnesses can be recovered without
inventing new dialogue or a convenient private admission. Comparisons require
all their sources. A personal shame is not automatic proof of murder.

Ballots use public comparisons and structured Suspect/Defend/Withdraw stances.
A single comparison plus the team's suspicion can move a witness above the
voting threshold; an unsupported accusation alone cannot. Defending lowers the
pressure, withdrawing removes the claim, and repeating it does not accumulate
weight. Private Detective findings and team chat are never automatic vote inputs.
The Mafia reacts to publicly useful witnesses when choosing a later target;
the Doctor can protect an exposed witness without learning the hidden solution.

## Interface and existing rules

The story picker and untimed briefing precede the case. The Case journal tab
contains the current phase, investigations, questions, revisions, evidence,
persuasion, and final ballot. The Dossier tab contains setup, cast, sources, and
reconstruction. Chat displays public accounts and private team conversation.
Each tab explains its purpose, and the journal explains the voting rules.

Every solo phase waits for Proceed. Confirming a Detective target does not end
the turn; the team can read its result before proceeding to dawn. The team can
proceed without investigating. There is no timer fallback in solo. Proceed from
the gathering opens the final vote; a confirmed ballot completes the count.

Solo still has one Mafia, one Doctor, four Villagers, and the Detective. Two
invited friends share that seat, its question allowance, actions, ballot, and
score. Lead controls case start/replay/end. Vote-out protection and the existing
final-chance night rule remain. Removing the sole Mafia ends the case in a town
win. A host-ended case also provides the reconstruction, even without a winner.

State is in memory. Reloads resume the browser session; a server restart ends
it. No external generation service is used. Data, authored responses, source
links, and structured decisions keep the case internally consistent.

## Validation and editorial checks

Tests cover all seven cases, source references, independent clue chains, hidden
content, fixed-role replay, aliases, one-question quotas, structured persuasion,
archived accounts, evidence-dependent ballots, public-information boundaries, and target
selection. Team, final-night, online game, scoring, and phase tests remain in place.
`scripts/check-solo-journal.cjs` checks structured questions, changed statements,
shared quotas, explicit phases, evidence persistence, truthful mode copy, mobile
layout, shared sessions, and the final reconstruction. Other browser checks
cover the existing online flows.

The prose review checks access and timing in each case: a sound cannot establish
a face; a signature can establish arrival without duration; a label cannot
establish contents; an old wrongdoing cannot establish the present murder.
Endings distinguish a solved case from a lost one. Post-verdict explanations
state hidden history without implying evidence was recovered in a Mafia victory.
