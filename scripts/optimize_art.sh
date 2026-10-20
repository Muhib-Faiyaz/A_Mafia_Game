#!/usr/bin/env bash
# Re-encode supplied originals without changing composition or game content.
set -euo pipefail
cd "$(dirname "$0")/.."
for source in static/images/opening/*.png; do
  ffmpeg -hide_banner -loglevel error -y -i "$source" -c:v libwebp -quality 84 -compression_level 6 "${source%.*}.webp"
done
for source in static/images/turns/*.jpg static/images/dead/*.jpg; do
  ffmpeg -hide_banner -loglevel error -y -i "$source" -vf scale=960:-2 -c:v libwebp -quality 78 -compression_level 6 "${source%.*}.webp"
done
