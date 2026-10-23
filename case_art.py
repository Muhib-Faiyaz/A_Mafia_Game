"""Resolve shipped case art without trusting paths in room state or client input."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'static/images/cases/manifest.json'
SCENES = ('mafia', 'doctor', 'detective', 'discussion', 'voting')


def manifest():
    try:
        return json.loads(MANIFEST.read_text(encoding='utf-8')).get('stories', {})
    except (OSError, ValueError, AttributeError):
        return {}


def safe_asset(value):
    if not isinstance(value, str) or not value.startswith('/static/images/cases/'):
        return None
    path = (ROOT / value.lstrip('/')).resolve()
    base = (ROOT / 'static/images/cases').resolve()
    if not path.is_relative_to(base) or path.suffix != '.webp' or not path.is_file():
        return None
    return value


def backgrounds(room):
    if room.get('mode') != 'solo' or room.get('tutorial'):
        return dict(desktop=None, mobile=None)
    phase = room.get('phase')
    scene = (room.get('night_step') if phase == 'night' else
             'voting' if phase == 'over' or (phase == 'day' and room.get('solo_voting')) else 'discussion')
    if scene not in SCENES:
        return dict(desktop=None, mobile=None)
    entry = manifest().get(room.get('scenario', {}).get('id'), {}).get('scenes', {}).get(scene, {})
    return {device: safe_asset(entry.get(device)) for device in ('desktop', 'mobile')}
