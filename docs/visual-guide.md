# Mafia: After Dark visual guide

The existing portrait artwork sets the identity: hand-inked Gothic environments with painterly material texture, dark slate shadows, worn timber and plaster, rain or snow beyond a window, and a small pool of amber light. Case art keeps that language while changing the architecture and equipment to match each story. A radio station is not dressed as a medieval castle; a seed repository remains a working laboratory.

## Rendering, colour and atmosphere

- Detailed, irregular black linework over painted surfaces; no photorealistic photographs, glossy 3D rendering, or flat vector substitutes.
- Charcoal and desaturated slate blue carry the night. Amber lamps provide readable focal points; restrained burgundy cloth and tarnished brass connect to the established interface. Snow and paper stay muted rather than bright white.
- Light comes from a plausible window, practical lamp, or theatre work light. Keep dark middle areas suitable for translucent game panels, with detail and props nearer the edges.
- Tension comes from empty space, interrupted work, weather and ordinary objects. No gore, bodies, weapons, readable text, faces, or culprit silhouettes.

## Continuity and story boundaries

Each case has one architectural vocabulary, repeated window frames, matching wood/metal finishes and consistent weather. Role scenes show different working zones within that location, not unrelated generic offices. Mafia imagery shows an empty night location rather than a specific killing or method. First-aid areas support the doctor mechanic without inventing a permanent doctor's office in every building.

The narrative agent approved the public prop families: radio reel and charts; hospice radiator and empty ward; train lamp and documents; archive drying racks and records; theatre work lights and interval bell; seed preparation bench and sealed sample; witness-house interview desk and statement. Do not add a suspect's distinctive clothing, personal equipment or portrait. Do not make text legible, alter a seal, identify a sample's contents, illustrate a hidden route, or visually establish a disputed timeline. Later story revisions require another spoiler check.

No new characters are designed for backgrounds. Existing character portraits remain authoritative. Recurring environmental details belong to the location, never to a suspect.

## Composition and platforms

Desktop exports are **1280 × 720 (16:9)**. Mobile exports are **540 × 960 (9:16)**. They use separate aspect-correct export regions; neither orientation is stretched. Role-pair source sheets contain two individually composed tall room vignettes, each with a central landscape band. Desktop selects that band, while mobile preserves the vertical window, furnishings and floor. Single-scene source sheets provide a wider room view with an intentional portrait focal area.

This is an adapted-crop production method rather than seventy independently generated paintings. Pair-sheet desktop regions start at 768 × 432 and are enlarged to the delivery dimensions; full-room voting sources are 1672 × 940–941 and provide desktop regions at 1664 × 936. Pair-sheet mobile regions start at 576 × 1024 and are reduced; voting mobile regions are 522 × 928 and receive a small enlargement. These backgrounds support an overlaid interface; they are not intended for close-up inspection as large prints. Never use CSS stretching or `background-size: 100% 100%`; preserve cover/contain aspect behaviour and serve the appropriate manifest variant.

Focal props should remain identifiable beside interface panels. Review at 390 × 844 and 1440 × 900 with the actual game interface, especially when the mobile browser chrome or keyboard changes the visible height. A desktop crop and portrait crop of the same scene may emphasize different objects; neither should carry exclusive evidence needed to solve the case.

## Files and scene contract

Delivery paths are `static/images/cases/<case-id>/<scene>-<desktop|mobile>.webp`. Scene keys are `mafia`, `doctor`, `detective`, `discussion`, and `voting`. IDs follow `data/solo_scenarios.json`. `manifest.json` is version 1 and maps each story title to those five scene keys, with `desktop`, `mobile`, and a plain-language `location` for each.

Compact full source sheets and provenance live under `_sources/`. `asset-catalog.json` records delivered dimensions, file sizes, SHA-256 digests and the source region. Generated PNG originals also remain in the workspace generation directory; compact WebP sources are retained in the repository. The generation tool provides original synthetic artwork, not licensed third-party photographs. Existing project illustrations were supplied as style references; no external artwork or character reference was downloaded.

WebP quality 82 with method 6 is the default delivery setting. Strip metadata from delivery files. Keep a full source sheet at quality 92 for review and future reframing; do not repeatedly encode delivery files from other lossy deliveries.

## Review sequence

The initial radio transmitter and first-aid room were exported in both orientations, inspected by the art agent, and reviewed by the coordinator before the remaining batch was authorized. Every subsequent source sheet needs visual inspection for continuity, text artifacts, frame boundaries, extra objects and accidental spoiler cues. Verify all manifest paths, aspect ratios and nonzero files before integration. Full in-game responsive and legibility checks remain the coordinator's responsibility and should be recorded separately from source-art inspection.
