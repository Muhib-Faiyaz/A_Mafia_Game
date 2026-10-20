import gzip
import unittest
from pathlib import Path
import app as game


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.client = game.app.test_client()

    def test_create_and_actions_return_authorized_view_when_requested(self):
        host = self.client.post('/api/create', json={'name': 'Host', 'include_state': True}).get_json()
        self.assertEqual(host['state']['me']['name'], 'Host')
        identity = {'code': host['code'], 'pid': host['pid'], 'include_state': True}
        for i in range(4):
            self.client.post('/api/join', json={'code': host['code'], 'name': f'Guest {i}'})
        state = self.client.post('/api/start', json=identity).get_json()['state']
        self.assertEqual(state['phase'], 'night')
        self.assertEqual(len(state['players']), 5)
        self.assertTrue(state['me']['role'])
        for player in state['players']:
            if not player['you']:
                self.assertIsNone(player['role'])
        response = self.client.post('/api/state', json=identity)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_legacy_api_and_unauthorized_requests(self):
        host = self.client.post('/api/create', json={'name': 'Host'}).get_json()
        self.assertNotIn('state', host)
        response = self.client.post('/api/start', json={'code': host['code'], 'pid': 'wrong', 'include_state': True})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('state', response.get_json())

    def test_text_compression_and_revalidation(self):
        for url in ('/', '/static/game.js', '/static/horror.css'):
            plain = self.client.get(url)
            compressed = self.client.get(url, headers={'Accept-Encoding': 'gzip'})
            self.assertEqual(compressed.headers.get('Content-Encoding'), 'gzip', url)
            self.assertEqual(gzip.decompress(compressed.data), plain.data)
            self.assertIn('Accept-Encoding', compressed.headers['Vary'])
            self.assertEqual(compressed.headers['Cache-Control'], 'no-cache')
            cached = self.client.get(url, headers={'Accept-Encoding': 'gzip', 'If-None-Match': compressed.headers['ETag']})
            self.addCleanup(cached.close)
            self.addCleanup(plain.close)
            self.addCleanup(compressed.close)
            self.assertEqual(cached.status_code, 304, url)

    def test_compressed_api_and_cacheable_art(self):
        response = self.client.post('/api/create', json={'name': 'Host', 'include_state': True}, headers={'Accept-Encoding': 'gzip'})
        self.assertEqual(response.headers.get('Content-Encoding'), 'gzip')
        self.assertIn(b'Host', gzip.decompress(response.data))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        response = self.client.get('/static/images/opening/town.webp')
        self.assertEqual(response.status_code, 200)
        self.assertIn('max-age=86400', response.headers['Cache-Control'])
        self.assertNotIn('Content-Encoding', response.headers)
        response.close()

    def test_optimized_art_pool_does_not_duplicate_legacy_images(self):
        room = {}
        paths = [game.choose_death_background(room) for _ in range(6)]
        self.assertEqual(len(set(paths)), 6)
        self.assertTrue(all(path.endswith('.webp') for path in paths))
        self.assertTrue(game.turn_background({'phase': 'night', 'night_step': 'doctor'}).endswith('doctor.webp'))
        for path in Path(game.app.static_folder, 'images').glob('*/*.webp'):
            self.assertLess(path.stat().st_size, 250000)
