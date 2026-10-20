# Turn backgrounds

These five JPG illustrations were supplied by the user in `other files.zip`
and copied unchanged with simple filenames:

- `detective.jpg`: detective office (first picture).
- `discussion.jpg`: discussion hall (second picture).
- `doctor.jpg`: clinic (third picture).
- `village.jpg`: normal village during the Mafia turn (fourth picture).
- `voting.jpg`: hall with ballot boxes (fifth picture).

Only installed pictures are advertised by the API, so missing files leave
the phase colors intact.
All living players see the current turn scene; eliminated players keep their
assigned death background over any turn scene.

## Optimized delivery

The game prefers the WebP copies. Opening art retains its full resolution;
turn and death art is encoded at 960px width for mobile screens. Original
PNG/JPG files remain available for regeneration and existing sessions. Run
`scripts/optimize_art.sh` with FFmpeg/libwebp installed to regenerate copies.
The asset pool treats different encodings of the same scene as one picture.
