import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app as game


class DeathBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'images' / 'dead'
        self.folder.mkdir(parents=True)
        patcher = patch.object(game.app, '_static_folder', self.temp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        game.rooms.clear()
        self.client = game.app.test_client()
        self.host = self.post('create', {'name': 'Host'})
        self.users = [self.host] + [self.post('join', dict(code=self.host['code'], name=f'Guest {i}')) for i in range(6)]
        self.post('start', self.host)
        self.room = game.rooms[self.host['code']]

    def post(self, action, data):
        response = self.client.post('/api/' + action, json=data)
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def install_images(self):
        for i in range(6):
            (self.folder / f'scene-{i}.jpg').touch()

    def test_unique_cycle_stable_assignment_and_restart(self):
        self.install_images()
        assigned = []
        for user in self.users:
            game.record_death(self.room, user['pid'], 'night')
            url = game.view(self.room, user['pid'])['me']['death_background']
            self.assertTrue(url.startswith('/static/images/dead/scene-'))
            game.record_death(self.room, user['pid'], 'night')
            self.assertEqual(game.view(self.room, user['pid'])['me']['death_background'], url)
            assigned.append(url)
        self.assertEqual(len(set(assigned[:6])), 6)
        self.assertNotEqual(assigned[5], assigned[6])
        game.start_game(self.room)
        self.assertEqual(self.room['death_backgrounds_used'], [])
        for user in self.users:
            self.assertIsNone(game.view(self.room, user['pid'])['me']['death_background'])

    def test_missing_images_and_rescue_keep_normal_background(self):
        game.record_death(self.room, self.host['pid'], 'vote')
        self.assertIsNone(game.view(self.room, self.host['pid'])['me']['death_background'])
        self.install_images()
        guest = self.users[1]['pid']
        game.record_rescue(self.room, guest)
        self.assertTrue(self.room['players'][guest]['alive'])
        self.assertIsNone(game.view(self.room, guest)['me']['death_background'])

    def test_reset_clears_backgrounds(self):
        self.install_images()
        game.record_death(self.room, self.host['pid'], 'vote')
        self.post('end', self.host)
        self.post('reset', self.host)
        self.assertIsNone(self.room['players'][self.host['pid']]['death_background'])
        self.assertEqual(self.room['death_backgrounds_used'], [])
