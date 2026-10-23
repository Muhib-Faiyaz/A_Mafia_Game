import json
import unittest
from unittest.mock import patch

import case_art
import solo_story


class CaseArtTests(unittest.TestCase):
    def test_missing_or_invalid_manifest_falls_back_without_breaking_state(self):
        room = dict(mode='solo', scenario={'id': 'unknown'}, phase='night', night_step='mafia')
        with patch.object(case_art, 'manifest', return_value={}):
            self.assertEqual(case_art.backgrounds(room), dict(desktop=None, mobile=None))
        for value in ('https://example.com/a.webp', '/static/images/cases/../../game.js',
                      '/static/images/cases/missing.webp', None):
            self.assertIsNone(case_art.safe_asset(value))

    def test_each_story_has_five_distinct_shipped_scenes_for_both_devices(self):
        manifest = json.loads(case_art.MANIFEST.read_text())
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(set(manifest['stories']), {case['id'] for case in solo_story.SCENARIOS})
        for story_id, story in manifest['stories'].items():
            with self.subTest(story=story_id):
                self.assertEqual(set(story['scenes']), set(case_art.SCENES))
                assets = []
                for scene, entry in story['scenes'].items():
                    self.assertTrue(entry['location'])
                    for device in ('desktop', 'mobile'):
                        path = entry[device]
                        self.assertEqual(case_art.safe_asset(path), path)
                        self.assertTrue(path.endswith(f'{scene}-{device}.webp'))
                        data = (case_art.ROOT / path.lstrip('/')).read_bytes()
                        self.assertEqual(data[:4], b'RIFF')
                        self.assertEqual(data[8:12], b'WEBP')
                        assets.append(data)
                self.assertEqual(len(set(assets)), 10, 'Each role and device needs its own asset')

    def test_scene_resolution_tracks_actual_phase_and_preserves_online_and_practice(self):
        story_id = solo_story.SCENARIOS[0]['id']
        room = dict(mode='solo', scenario={'id': story_id}, phase='night')
        for scene in ('mafia', 'doctor', 'detective'):
            room['night_step'] = scene
            self.assertIn(scene + '-desktop.webp', case_art.backgrounds(room)['desktop'])
        room.update(phase='day', solo_voting=False)
        self.assertIn('discussion-desktop.webp', case_art.backgrounds(room)['desktop'])
        room['solo_voting'] = True
        self.assertIn('voting-mobile.webp', case_art.backgrounds(room)['mobile'])
        for extra in ({'mode': 'online'}, {'tutorial': True}):
            self.assertEqual(case_art.backgrounds(dict(room, **extra)), dict(desktop=None, mobile=None))


if __name__ == '__main__':
    unittest.main()
