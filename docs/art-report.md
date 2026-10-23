# Art generation report

## Delivered

Seven production cases each have five distinct location zones (`mafia`, `doctor`, `detective`, `discussion`, `voting`) and two aspect-correct WebP variants: **70 delivered files**, 1280 × 720 desktop and 540 × 960 mobile. Their total is **7,451,692 bytes (7.11 MiB)**; individual files range from 55,710 to 214,788 bytes, with a median of 101,263 bytes.

| Case | Delivered bytes |
| --- | ---: |
| The Ninth Photograph | 1,136,208 |
| A Room Kept Warm | 978,784 |
| The Witness in Carriage Six | 1,145,190 |
| What the River Returned | 1,297,026 |
| The Last Dress Rehearsal | 1,019,098 |
| The Winter Seed | 883,520 |
| The Quiet Sentence | 991,866 |

The version-1 [manifest](../static/images/cases/manifest.json) contains the agreed story/scene/desktop/mobile/location contract. The [asset catalog](../static/images/cases/asset-catalog.json) records every delivered dimension, byte count, SHA-256 digest, source file, native source dimensions, and crop region. [The visual guide](visual-guide.md) explains the shared style, scene boundaries and composition rules.

All artwork was genuinely generated through `OpenAI image_gen.imagegen` on 2026-10-23 using the existing project's art as style references. No external photographs, downloaded artwork, font packs, character likenesses or new asset licenses were introduced. The images contain no newly designed characters. Existing character portraits remain unchanged.

## Inspection and decisions

Inspected `data/solo_scenarios.json`, the user’s attached development plan, existing opening/turn/role asset organization, `scripts/optimize_art.sh`, and the existing doctor and Gothic hall artworks. No applicable `AGENTS.md` was found in the workspace. The existing visual identity is ink-and-paint Gothic illustration, with slate shadows, practical amber light, worn material textures and burgundy accents.

The radio transmitter and first-aid room formed the initial representative set. Both desktop and mobile exports were viewed by the art agent, then reviewed and approved by the coordinator before bulk generation. Each later case used its own source sheet as the reference for subsequent room zones. The narrative agent approved the public establishing props. No suspect-specific equipment, hidden routes, readable evidence, death methods, victims or culprit portraits were requested.

One early hospice generation wrongly carried coastal scenery from the radio reference. It was rejected before delivery and regenerated with snowy mountain slopes. All 21 accepted source sheets were visually inspected for setting, consistent rendering, panel boundaries, faces, gore, legible text and accidental spoiler cues. The coordinator also reviewed the snowy hospice, industrial seed repository and train sources. All 70 exported crops were inspected together in desktop and mobile contact sheets; the crops retain the intended room zones without stretching.

## Sources and reproducibility

The accepted set contains **35 illustrated room zones across 21 full source sheets**, adapted into 70 deliveries. Four role zones per case come from two diptych sheets; voting receives a full-width view of another part of the communal room. There were 22 generation calls including the rejected hospice sheet. This avoided independently redesigning the same location in seventy calls.

Twenty-one compact, full-sheet source WebPs are retained under `static/images/cases/_sources/`, totaling **10,578,714 bytes (10.09 MiB)**. [Provenance](../static/images/cases/_sources/provenance.json) records the generation tool, date, prompt or representative prompt summary, input references, original workspace PNG paths, native dimensions, bytes and hashes. Original PNG outputs remain in `/workspace/generated_images/`; their bulky copies are not duplicated in the repository. Source WebPs use quality 92; deliveries use quality 82, method 6, with metadata stripped.

Rebuild from the reviewed compact sources with:

```sh
python static/images/cases/_sources/export_assets.py
```

The script reads [production.json](../static/images/cases/_sources/production.json), checks source/crop bounds and exact ratios, exports all deliveries, and writes the manifest and catalog only after all 70 distinct files validate. It requires the existing ImageMagick `magick` executable. No package installation was necessary. Pillow was already installed and used for independent decode verification.

## Verification and limits

- Export script: **passed** — seven cases, 70 unique hashes, correct dimensions, nonzero files, bounded aspect-correct crop regions and all manifest paths.
- Independent Pillow decode/verify: **70/70 passed**, all images identify as WebP with the required dimensions; no duplicate content hashes.
- Source and delivery contact-sheet review: **passed** for the intended atmospheric art scope. Contact sheets are temporary review artifacts in `/tmp/art-review-02.webp`, `/tmp/art-review-03.webp`, `/tmp/art-deliveries-desktop.webp` and `/tmp/art-deliveries-mobile.webp`.
- Coordinator integration: all 155 server tests passed, including manifest validation. `node scripts/check-case-art.cjs` decoded all 70 images in Chromium and verified five live phases selecting the correct mobile/desktop variant at 320/390/1440px without horizontal overflow. The coordinator fixed the older `horror.css` overlay's responsive selection and visually inspected in-game portrait Detective and desktop voting captures.

Desktop and mobile are carefully adapted crops, not seventy independent compositions. Pair-sheet desktop regions are natively 768 × 432 and are enlarged to 1280 × 720; their small details will look softer on very large displays. Pair-sheet portrait regions are 576 × 1024 and are reduced to 540 × 960. Voting sources are 1672 × 940–941; desktop crops are 1664 × 936 and mobile crops are 522 × 928, with a small portrait enlargement. There is no orientation stretching. Every source/crop dimension is recorded rather than inferred from the exported resolution.

No case is missing an asset and no placeholder stands in for required art. Minor generated furniture/window perspective variation remains possible; these are atmosphere illustrations, not floor-plan evidence. No evidence required to solve a case is exclusive to one orientation. The tutorial/practice case and multiplayer keep their existing fallback artwork because the agreed case manifest covers the seven production stories. After future narrative or layout changes, manually recheck spoiler boundaries and readability on actual mobile devices and large monitors.

## Skills and tooling assessment

Reviewed the supplied skill catalog and independently queried the supported cloud and executor skill registries. The registry exposed only the managed runtime and environment-onboarding skills; no art-generation or image-production skill was available. The existing `image_gen.imagegen`, ImageMagick and Pillow tools directly supported this work, so no additional skill was downloaded or installed and no installation script was run.

Used [cloud-environment-runtime SKILL.md](skill://plugin_connector_1p_c5b7d5df5d7081918f2c4be5a633ed5d/cloud-environment-runtime/SKILL.md) and its networking reference at the start, inspected `/etc/codex/network-policy.json`, and queried environment status before generation. The snapshot exposed restricted HTTP policy with runtime enforcement state `unknown`, no VPN and no configured outbound credentials; no credential values were inspected or printed. Generation used the provided service tool, with no direct external asset-download commands. The onboarding skill did not materially help art production and was not applied. No skill imposed a further approval gate; the coordinator's representative-image validation followed the user's explicit art workflow.

Only `static/images/cases/`, `docs/visual-guide.md` and this report were modified by the art agent. No application, CSS, JavaScript, narrative data, tests, commits or pushes were changed by this agent.
