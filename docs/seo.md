# Search visibility for Mafia · After dark

The public page targets people looking for an **online Mafia game** or a browser version of the **Mafia board game**. The text explains what the game actually offers: 3–20 players, private room codes, optional bots, Doctor and Detective roles, and no account or download.

## Skills installed and applied

- [SEO](../.agents/skills/seo/SKILL.md): crawlable public content, descriptive titles and snippets, canonical URLs, sitemap, crawler controls, accurate structured data, and rendered-page validation.
- [Accessibility](../.agents/skills/accessibility/SKILL.md): descriptive headings, a keyboard skip link, form labels, and matching visible/accessibility names.

Both are unchanged copies from Addy Osmani's `web-quality-skills` at revision `afa8da942115f2961fdbfa80807ea0b232ff6c00`. Each package includes its MIT license and source record. Existing performance and Core Web Vitals skills remain available. The user's requested autoplay and existing sound controls are retained.

## Implemented

- Server-rendered landing content, including create/join controls, a clear game description, and rules. The JavaScript landing view uses the same copy; regression tests detect drift. The game remains a client-driven app after entry.
- A descriptive title and meta description, Open Graph and Twitter sharing metadata, and schema.org `WebApplication` JSON-LD describing the free browser game. No fabricated reviews, ratings, or ranking claims.
- A single canonical homepage. `/index.html` and `/static/index.html` redirect permanently to `/`.
- `/robots.txt` allows the public page and rendering assets. API and health responses carry `X-Robots-Tag: noindex`; the robots file also excludes them. These are indexing directives, not access controls.
- A sitemap containing only the canonical public homepage, with no private room codes, session identities, fake last-modified dates, or query strings.
- A keyboard “Skip to game” link and a corrected accessible name for the brand link.

## Production URL

Set `SITE_URL` to the production origin, including `https://`, without a path, query, credentials, or fragment. Railway's injected `RAILWAY_PUBLIC_DOMAIN` is used automatically when `SITE_URL` is absent. This single configuration supplies canonical, sitemap, and sharing URLs. Incoming Host and forwarded headers never define the public origin.

The user deferred choosing a domain. Until one of those variables is available, URL-specific metadata is omitted, `robots.txt` omits a sitemap declaration, and `/sitemap.xml` returns 503 with an explanation. The rest of the SEO improvements work locally. No environment or hosting configuration was changed by this coding task.

After deployment:

1. Verify `/` returns 200, `/robots.txt` permits the homepage and assets, and `/sitemap.xml` contains the final HTTPS homepage.
2. Verify the canonical and Open Graph URL point to that same homepage, and the sharing image is publicly accessible.
3. Verify the site's ownership in Google Search Console, submit `/sitemap.xml`, and request indexing of the homepage. This needs the site owner's account; no submission was performed here.
4. Monitor indexed pages and query impressions. Indexing, rankings, rich results, and social-card display are controlled by the respective services and cannot be guaranteed. Consider useful guides and links from relevant communities after launch; avoid keyword stuffing or manufactured backlinks.

## Validation

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /workspace/.venvs/a-mafia-game/bin/python -m unittest discover -s tests -v
node --check static/game.js
node tests/test_music.cjs
# Start the app locally on port 5050 before this browser check:
node scripts/check-seo.cjs http://127.0.0.1:5050
```

The browser check uses Playwright and `/usr/bin/chromium` from the cloud development environment. It checks no-JavaScript content, keyboard navigation, metadata, mobile/desktop overflow, and creating/leaving a room. The Python suite covers schema data, URL consistency, query/host isolation, redirects, sitemap behavior, API indexing headers, and existing gameplay/delivery behavior.

Local Lighthouse mobile navigation audits measured SEO at **90 before** and **100 after** the changes. The final accessibility audit also scored **100**, with no automated audit failures. These are lab checks against a local server, not field Core Web Vitals, a comprehensive accessibility certification, proof of indexing, or a prediction of ranking. Live production, Search Console, and external structured-data validation remain pending deployment.
