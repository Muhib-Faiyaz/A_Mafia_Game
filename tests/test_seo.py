import json
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree
from unittest.mock import patch
import app as game


class SeoTests(unittest.TestCase):
    def setUp(self):
        self.config = patch.dict(game.app.config, SITE_URL='https://mafia.example')
        self.config.start()
        self.addCleanup(self.config.stop)
        self.client = game.app.test_client()

    def test_home_is_useful_without_javascript_and_has_accurate_schema(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('Online Mafia Game', html)
        self.assertIn('name="description"', html)
        self.assertIn('Play the Mafia board game online', html)
        self.assertIn('How to play Mafia with friends', html)
        self.assertIn('id="online-play"', html)
        self.assertIn('id="solo-run"', html)
        self.assertIn('<noscript>', html)
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(schema['@type'], 'WebApplication')
        self.assertEqual(schema['offers']['price'], '0')
        self.assertEqual(schema['url'], 'https://mafia.example/')
        self.assertNotIn('aggregateRating', schema)

    def test_canonical_sitemap_and_social_urls_agree_and_ignore_request_host(self):
        html = self.client.get('/?code=PRIVATE', headers={'Host': 'other.example', 'X-Forwarded-Host': 'attacker.example'}).get_data(as_text=True)
        self.assertIn('rel="canonical" href="https://mafia.example/"', html)
        self.assertIn('property="og:url" content="https://mafia.example/"', html)
        self.assertIn('name="twitter:image" content="https://mafia.example/static/images/opening/town.png"', html)
        self.assertNotIn('PRIVATE', html)
        self.assertNotIn('attacker.example', html)
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/xml')
        tree = ElementTree.fromstring(response.data)
        locations = tree.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        self.assertEqual([loc.text for loc in locations], ['https://mafia.example/'])
        robots = self.client.get('/robots.txt').get_data(as_text=True)
        self.assertIn('Sitemap: https://mafia.example/sitemap.xml', robots)
        self.assertNotIn('Disallow: /static/', robots)

    def test_unconfigured_site_does_not_publish_invented_or_local_urls(self):
        game.app.config['SITE_URL'] = ''
        html = self.client.get('/').get_data(as_text=True)
        self.assertNotIn('rel="canonical"', html)
        self.assertNotIn('localhost', html)
        self.assertNotIn('Sitemap:', self.client.get('/robots.txt').get_data(as_text=True))
        self.assertEqual(self.client.get('/sitemap.xml').status_code, 503)

    def test_invalid_origin_is_not_used(self):
        for value in ['javascript:alert(1)', 'https://user:password@example.com', 'https://example.com/path', 'https://example.com/?x=1']:
            game.app.config['SITE_URL'] = value
            self.assertEqual(game.public_site_url(), '')

    def test_duplicate_documents_redirect_and_private_endpoints_are_not_indexable(self):
        for path in ['/static/index.html', '/index.html']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response.headers['Location'], '/')
        for path in ['/health', '/api/state']:
            response = self.client.get(path)
            self.assertIn('noindex', response.headers['X-Robots-Tag'])
        robots = self.client.get('/robots.txt').get_data(as_text=True)
        self.assertIn('Disallow: /api/', robots)
        self.assertIn('Disallow: /health', robots)

    def test_initial_and_client_landing_copy_match(self):
        root = Path(game.__file__).parent
        script = (root / 'static/game.js').read_text()
        home = re.search(r'function home\(\) \{\s*return `(.*?)`;', script, re.S).group(1)
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn(home, html)
        self.assertEqual((root / 'static/index.html').read_bytes(), (root / 'index.html').read_bytes())
