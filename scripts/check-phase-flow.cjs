// Run against the local Flask/Gunicorn server, then inspect its normal API/UI.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, data) {
  const response = await fetch(base + '/api/' + route, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data),
  });
  const result = await response.json();
  assert.equal(response.status, 200, JSON.stringify(result));
  return result;
}
(async () => {
  const host = await post('create', {name: 'Phase host'});
  const users = [host];
  for (let i = 0; i < 6; i++) users.push(await post('join', {code: host.code, name: 'Phase guest ' + i}));
  await post('settings', {...host, mafia_count: 2, special_roles: true});
  await post('start', host);
  const byRole = {};
  for (const identity of users) {
    const state = await post('state', identity);
    (byRole[state.me.role] ||= []).push(identity);
  }
  const detective = byRole.detective[0], doctor = byRole.doctor[0], villager = byRole.town[0];
  const browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  const errors = [];
  async function openPlayer(identity) {
    const context = await browser.newContext({viewport: {width: 390, height: 844}});
    await context.addInitScript(identity => localStorage.setItem('mafia', JSON.stringify(identity)), identity);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.waitForFunction(() => !!state);
    return page;
  }
  async function reachDetective() {
    for (const identity of byRole.mafia) await post('act', {...identity, target: villager.pid});
    assert.equal((await post('state', host)).night_step, 'doctor');
    await post('act', {...doctor, target: villager.pid});
    assert.equal((await post('state', host)).night_step, 'detective');
  }
  async function dismissDeath(page) {
    if (await page.locator('#death-notice').evaluate(el => el.open)) await page.locator('#dismiss-death').click();
  }
  try {
    await reachDetective();
    const detPage = await openPlayer(detective);
    const observer = await openPlayer(villager);
    await detPage.locator(`[data-player="${byRole.mafia[0].pid}"]`).click();
    await detPage.locator('#confirm-action').click();
    await detPage.locator('#investigation-dialog[open]').waitFor();
    assert.match(await detPage.locator('#investigation-title').innerText(), /was right/);
    assert.match(await detPage.locator('#investigation-result').innerText(), /is Mafia/);
    assert.match(await detPage.locator('#investigation-reminder').innerText(), /Convince the others/);
    await observer.waitForFunction(() => state?.phase === 'day');
    assert.equal(await observer.locator('#investigation-dialog').evaluate(el => el.open), false);
    assert.equal(await observer.locator('#app').innerText().then(text => text.includes('Convince the others')), false);
    await detPage.screenshot({path: '/tmp/mafia-detective-result.png'});
    await detPage.locator('#dismiss-investigation').click();
    await dismissDeath(detPage);
    await dismissDeath(observer);
    await detPage.reload();
    await detPage.waitForFunction(() => state?.phase === 'day');
    assert.equal(await detPage.locator('#investigation-dialog').evaluate(el => el.open), false, 'Acknowledged result does not replay on reload');
    await observer.locator('#proceed-vote').click();
    await observer.waitForFunction(() => state?.discussion.ready === 1);
    assert.equal(await observer.locator('#proceed-vote').isDisabled(), true);
    assert.match(await observer.locator('#proceed-count').innerText(), /1\/7/);
    await detPage.waitForFunction(() => state?.discussion.ready === 1);
    assert.ok((await detPage.locator('#messages-town').innerText()).includes('voted to proceed'));
    await detPage.screenshot({path: '/tmp/mafia-discussion-ready.png'});
    for (const identity of users.filter(user => user !== villager)) await post('proceed', identity);
    await detPage.waitForFunction(() => state?.voting);
    assert.equal(await detPage.locator('#proceed-vote').count(), 0);
    for (const identity of users) await post('vote', {...identity, target: 'skip'});
    await reachDetective();
    await detPage.waitForFunction(() => state?.night_step === 'detective' && state?.day === 2);
    await detPage.locator(`[data-player="${villager.pid}"]`).click();
    await detPage.locator('#confirm-action').click();
    await detPage.locator('#investigation-dialog[open]').waitFor();
    assert.match(await detPage.locator('#investigation-title').innerText(), /was wrong/);
    assert.match(await detPage.locator('#investigation-result').innerText(), /not Mafia/);
    assert.deepEqual(errors, []);
    console.log('Phase browser checks passed: correct/wrong private result, persuasion reminder, acknowledgment, ready counter/chat, unanimous progression, next night.');
  } finally {
    await browser.close();
    await post('end', host);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
