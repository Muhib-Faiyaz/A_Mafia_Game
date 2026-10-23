# Story complexity

The stars describe the reasoning in the authored evidence route. They do not
predict a player's win rate, reading speed, or luck with a night investigation.
There is no need for the seven public cases to occupy every rating: these cases
already share six witnesses, several compromised accounts, and a fixed solution.
The separate practice exercise provides a very easy starting point.

| Stars | Label | Reasoning score |
| --- | --- | --- |
| 1 | Very easy | 0–2 |
| 2 | Easy | 3–4 |
| 3 | Moderate | 5–6 |
| 4 | Difficult | 7–8 |
| 5 | Very difficult | 9 or more |

## Reproducible measurements

The case's `complexity` object contains `stars`, `label`, `reason`, and `factors`.
The authoritative calculation lives in [case_details.py](../case_details.py).
It reads the existing clue/comparison ledger and a small, reviewable `reasoning`
annotation in the case JSON. UI code does not assign stars.

| Factor | Measurement | Contribution to score |
| --- | --- | --- |
| `clue_chain_length` | Largest number of distinct required clue IDs in a positive comparison. The engine has flat evidence sets, so this measures the length of the supported comparison, not recursive inference depth. | `max(0, length - 2)` |
| `cross_source_joins` | Largest number of distinct sources in a positive comparison, minus one. Multiple records from one witness count as one source; all scene exhibits share one scene source. | `max(0, joins - 1)` |
| `timing_checks` | Zero, one, or two independently described order/interval checks necessary to evaluate the accusation. Each annotation names at least two existing clue IDs and explains the check. | 0–2 |
| `false_leads` | Number of negative comparisons which explain why another person's genuine wrongdoing does not establish the main accusation. Mere secrets are not counted. | Capped at 2 |
| `interpretation_checks` | Zero, one, or two different conceptual distinctions needed to use the evidence: for example, a record's date versus a person's location, or a label's continuity versus an object's identity. Each annotation names its sources and the actual distinction. | 0–2 |

Add the five contributions, then apply the table above. Counts of suspects,
paragraphs, atmospheric detail, and unrelated secrets do not add difficulty.
Timing and interpretation are author-reviewed annotations rather than a keyword
scan. Reviewers can follow their `requires` IDs to check the actual demands;
adding an unsupported annotation is an authoring error, not a higher difficulty.

The two graph maxima measure the most demanding comparisons in a case and may
come from different comparisons. These are workload measurements, not claims
that every supporting item proves guilt alone. Scores and thresholds are a
consistent editorial scale, not an empirically calibrated difficulty model.

## Current measurements

| Case | Evidence length | Source joins | Timing | False leads | Interpretation | Score | Stars |
| --- | --- | --- | --- | --- | --- | --- | --- |
| The Ninth Photograph | 4 | 2 | 2 | 1 | 2 | 8 | 4 |
| A Room Kept Warm | 3 | 2 | 1 | 1 | 1 | 5 | 3 |
| The Witness in Carriage Six | 3 | 2 | 2 | 1 | 1 | 6 | 3 |
| What the River Returned | 4 | 2 | 1 | 1 | 2 | 7 | 4 |
| The Last Dress Rehearsal | 3 | 2 | 2 | 1 | 2 | 7 | 4 |
| The Winter Seed | 4 | 3 | 1 | 1 | 2 | 8 | 4 |
| The Quiet Sentence | 4 | 3 | 2 | 1 | 2 | 9 | 5 |
| The Missing Practice Dispatch (separate practice) | 3 | 2 | 0 | 0 | 0 | 2 | 1 |

The practice has direct identification corroborated by a signed collection,
with no false lead or subtle time/meaning distinction. The public mysteries
require several accounts, source limitations, and an explained distraction.
The Quiet Sentence also requires a physical route, a disclosure sequence, and
the distinction between knowing an objection and knowing its private wording.
These are the reasons for the distribution; ratings were not spread to fill a
selection menu.

## Authoring and publication

1. Preserve one fixed culprit, a different Doctor, and a fixed pre-game timeline.
2. Write positive and negative comparisons with the real supporting clue IDs.
3. Annotate each essential timing/interpretation check with `requires` and `note`.
   Cap each category at two: extra examples of the same demand do not inflate it.
4. Regenerate the stored object with `case['complexity'] = complexity(case)`.
5. Run `validate_case(case)` and the focused tests below. Review the prose as
   well: matching IDs alone cannot prove a semantic interpretation is sound.

`complexity(case)` returns a fresh dictionary with only the four public fields
and five numeric factors. Its reason is generated from these measurements and
cannot contain a culprit, private reasoning note, solution, or arbitrary extra
metadata from the stored object. Recomputing also keeps a stale stored rating
from reaching the API; validation reports the mismatch for correction.

```sh
python -m unittest discover -s tests -p 'test_case_details.py' -v
```

This command checks every stored case, all five thresholds, stale/private
metadata handling, incident reveal gates, and the practice evidence/vote path.
