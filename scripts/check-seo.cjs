// Run against a local server: node scripts/check-seo.cjs [http://127.0.0.1:5050]
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
(async () => {
  const browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  try {
    const plain = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 844}});
    const staticPage = await plain.newPage();
    await staticPage.goto(base);
    await staticPage.getByRole('heading', {name: 'Play Mafia online. Trust no one.'}).waitFor();
    await staticPage.getByRole('heading', {name: 'Play the Mafia board game online'}).waitFor();
    assert.match(await staticPage.locator('noscript').innerText(), /Enable JavaScript/);
    assert.equal(await staticPage.locator('h1').count(), 1);
    await plain.close();
    const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.keyboard.press('Tab');
    assert.equal(await page.locator(':focus').textContent(), 'Skip to game');
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'app');
    assert.match(await page.title(), /Online Mafia Game/);
    assert.equal(await page.locator('meta[name="description"]').count(), 1);
    for (const width of [390, 1440]) {
      await page.setViewportSize({width, height: 900});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No overflow at ${width}px`);
    }
    await page.locator('#online-play').click();
    await page.locator('#name').fill('SEO check');
    await page.locator('#entry button[type="submit"]').click();
    await page.waitForFunction(() => state?.phase === 'lobby');
    assert.equal(await page.locator('.game-overview').count(), 0, 'Public introduction gives way to lobby');
    await page.locator('#leave').click();
    await page.waitForFunction(() => !session);
    await page.getByRole('heading', {name: 'Play the Mafia board game online'}).waitFor();
    assert.deepEqual(errors, []);
    console.log('SEO browser checks passed: no-JS content, keyboard skip, metadata, mobile/desktop layout, create/leave room.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
