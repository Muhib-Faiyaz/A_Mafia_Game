# Eliminated-player illustrations

These six JPG illustrations were supplied by the user in `dead file.zip`.
They are copied unchanged, with simple filenames for serving as game assets.

The server randomly assigns an image when a player dies. The assignment
persists through refreshes until the next game. All six images are used
before a new cycle begins, and adjacent deaths never share the same image.
With more than six deaths, images repeat only after the pool is exhausted.
Living and rescued players keep the normal phase backgrounds.

## Optimized delivery

The game prefers the WebP copies. Opening art retains its full resolution;
turn and death art is encoded at 960px width for mobile screens. Original
PNG/JPG files remain available for regeneration and existing sessions. Run
`scripts/optimize_art.sh` with FFmpeg/libwebp installed to regenerate copies.
The asset pool treats different encodings of the same scene as one picture.
