#!/usr/bin/env python3
"""Rebuild case deliveries and manifest from the reviewed compact source sheets.

Requires ImageMagick's `magick`. Run from any working directory. Crops are
explicit production adaptations; every output preserves its intended ratio.
"""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path(__file__).with_name('production.json')


def dimensions(path):
    return tuple(map(int, subprocess.check_output(
        ['magick', 'identify', '-format', '%w %h', str(path)], text=True
    ).split()))


def main():
    production = json.loads(PLAN.read_text())
    manifest = {'version': 1, 'stories': {}}
    assets = []
    for story in production['stories']:
        case = story['id']
        entry = {'title': story['title'], 'scenes': {}}
        manifest['stories'][case] = entry
        for scene in story['scenes']:
            source = ROOT / scene['source']
            source_width, source_height = dimensions(source)
            paths = {}
            for orientation, size in [('desktop', (1280, 720)), ('mobile', (540, 960))]:
                x, y, width, height = scene['crops'][orientation]
                if x < 0 or y < 0 or x + width > source_width or y + height > source_height:
                    raise ValueError(f'Out-of-bounds crop: {case}/{scene["id"]}')
                if width * size[1] != height * size[0]:
                    raise ValueError(f'Crop would distort aspect: {case}/{scene["id"]}')
                relative = f'{case}/{scene["id"]}-{orientation}.webp'
                target = ROOT / relative
                target.parent.mkdir(exist_ok=True)
                subprocess.run([
                    'magick', str(source), '-crop', f'{width}x{height}+{x}+{y}',
                    '+repage', '-resize', f'{size[0]}x{size[1]}', '-strip',
                    '-quality', '82', '-define', 'webp:method=6', str(target)
                ], check=True)
                if dimensions(target) != size:
                    raise ValueError(f'Unexpected delivery dimensions: {target}')
                content = target.read_bytes()
                paths[orientation] = '/static/images/cases/' + relative
                assets.append({
                    'path': relative, 'width': size[0], 'height': size[1],
                    'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                    'source': scene['source'], 'source_width': source_width,
                    'source_height': source_height, 'source_region_xywh': [x, y, width, height],
                    'origin': 'OpenAI image_gen.imagegen; generated case environment',
                })
            entry['scenes'][scene['id']] = {**paths, 'location': scene['location']}
    if len(assets) != 70 or len({a['sha256'] for a in assets}) != 70:
        raise ValueError('Expected seventy distinct delivery files')
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'asset-catalog.json').write_text(json.dumps({
        'version': 1, 'generated_on': production['generated_on'], 'assets': assets,
        'total_delivery_bytes': sum(a['bytes'] for a in assets),
    }, indent=2) + '\n')
    print(f'Validated {len(manifest["stories"])} cases, {len(assets)} distinct WebPs; '
          f'{sum(a["bytes"] for a in assets):,} delivery bytes.')


if __name__ == '__main__':
    main()
