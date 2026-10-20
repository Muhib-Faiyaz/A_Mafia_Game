# Opening artwork

`town.png` and `hall.png` are background edits of the user's two screen mockups
from `opening files.zip`, prepared with the image generation tool. The edits
remove baked-in text, form panels, and the phone frame while retaining the
village, shadow figure, gothic hall, candles, and red-mist art direction.
Real HTML controls provide the titles, room code, players, inputs and buttons.

References: `compressed-op_mob_1.jpg` and `compressed-op_mob2.jpg` in the upload.

## Optimized delivery

The game prefers the WebP copies. Opening art retains its full resolution;
turn and death art is encoded at 960px width for mobile screens. Original
PNG/JPG files remain available for regeneration and existing sessions. Run
`scripts/optimize_art.sh` with FFmpeg/libwebp installed to regenerate copies.
The asset pool treats different encodings of the same scene as one picture.
