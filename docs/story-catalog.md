# Solo story catalog and writing sources

Choose a title in **Solo run**, or select **Random story**. Random avoids the most
recent case played in the browser; explicitly selecting a title can replay it.
Each case has six witnesses, one fixed Mafia culprit, and a consistent timeline.
Replaying a case keeps that solution. This list does not identify any culprit.

| Story | Mystery premise | Writing source |
| --- | --- | --- |
| **The Ninth Photograph** | At an isolated radio station, a recorded voice and an uncropped rescue photograph threaten the accepted account of an old wreck. | Combines **The Ninth Bell** and **The House Below the Tide**, originally written using **novel-writing**. |
| **A Room Kept Warm** | A hospice trustee is dead, a trust amendment is missing, and an empty room remains inexplicably heated. | Retained original **novel-writing** case. |
| **The Witness in Carriage Six** | A witness dies on a stranded train, leaving a missing deposition and conflicting accounts of the last station. | Retained original **novel-writing** case. |
| **What the River Returned** | A flood returns records thought destroyed, and an archivist dies before explaining which boundary mattered. | Retained original **novel-writing** case. |
| **The Last Dress Rehearsal** | A theatre's final rehearsal exposes a death, a disputed cue, and missing charity accounts. | Retained original **novel-writing** case. |
| **The Winter Seed** | A seed auditor is killed while a sealed reference sample becomes the last reliable check on a relief shipment. | Retained original **novel-writing** case. |
| **The Quiet Sentence** | A witness corrects one sentence before a hearing; the liaison who accepts it is killed inside a protection house. | Wholly new case using **Story Skills genre-craft and scene-craft**. |

The seven selections comprise five retained cases, one combined case, and one
new case. The two earlier stories that form **The Ninth Photograph** are now
represented by that combined selection rather than separate entries.

## Skills retained and added

The existing [novel-writing skill](../.agents/skills/novel-writing/SKILL.md)
remains installed. Its source is
[github.com/wgwtest/novel-writing](https://github.com/wgwtest/novel-writing), pinned
to `838729695148008d42c01bd7c3c0c1a5c15de830` under the MIT license. It guided
character introductions, limited knowledge, causal scenes, distinct dialogue,
fixed chronology, and revisions of the original mysteries.

The added Story Skills packages come from
[github.com/danjdewhurst/story-skills](https://github.com/danjdewhurst/story-skills),
pinned to `57121ee512c6d4218a285c6991193347944f31b0`, also under the MIT license:

- [Genre craft](../.agents/skills/story-skills/genre-craft/SKILL.md): fair-play
  clues, separate motive/means/opportunity, delayed significance, and red
  herrings with an explanation.
- [Scene craft](../.agents/skills/story-skills/scene-craft/SKILL.md): dialogue
  subtext, concessions under pressure, distinct voices, and openings anchored
  in an interrupted task.

**The Quiet Sentence** is original prose applying those methods, not a copied
upstream story. The skill files, references, license, and
[download/application record](../.agents/skills/story-skills/SOURCE.md) are kept
alongside novel-writing. No external text-generation service is required.

Game canon remains in [solo_scenarios.json](../data/solo_scenarios.json): the clue
ledger, source links, witness corrections, timeline, and final reconstruction
are checked against that existing format. Full solutions appear in the Dossier
after the case ends. See [solo story design](solo-story-design.md) for the manual
rounds, question allowance, and voting model.
