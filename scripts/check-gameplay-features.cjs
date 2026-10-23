const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body, status = 200, retries = 2) {
  const response = await fetch(base + '/api/' + route, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await response.json();
  if (route === 'team-chat' && status === 200 && response.status === 400 && data.error === 'Slow down a little.' && retries > 0) {
    await new Promise(resolve => setTimeout(resolve, 1100));
    return post(route, body, status, retries - 1);
  }
  assert.equal(response.status, status, data.error || 'Unexpected response');
  return data;
}
async function click(page, selector) {
  await page.waitForFunction(() => !busy);
  await page.locator(selector).click();
  await page.waitForFunction(() => !busy);
}
async function tab(page, name) {
  await page.locator(`[data-solo-tab="${name}"]`).click();
  assert.equal(await page.locator(`#solo-tab-${name}`).isVisible(), true);
}
async function dismiss(page) {
  for (let i = 0; i < 12; i++) {
    if (await page.locator('#investigation-dialog').evaluate(el => el.open)) await page.locator('#dismiss-investigation').click();
    else if (await page.locator('#death-notice').evaluate(el => el.open)) await page.locator('#dismiss-death').click();
    else break;
  }
}
(async () => {
  const browser = await chromium.launch({executablePath:'/usr/bin/chromium', headless:true, args:['--no-sandbox']});
  const identities = [], errors = [];
  try {
    const context = await browser.newContext({viewport:{width:390,height:844}}), page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.locator('#solo-run').click();
    await page.waitForFunction(() => storyCatalog.length === 7);
    await page.locator('#story-choice').selectOption(await page.evaluate(() => storyCatalog[0].id));
    assert.match(await page.locator('.story-preview .complexity-stars').getAttribute('aria-label'), /out of 5 stars/);
    await page.locator('#name').fill('Practice Reader');
    await click(page, '#practice-tutorial');
    await page.waitForFunction(() => state?.tutorial && state.phase === 'lobby');
    const practice = await page.evaluate(() => session); identities.push(practice);
    assert.match(await page.locator('#practice-guide').textContent(), /same investigations/);
    await click(page, '#start');
    assert.equal(await page.locator('#nav [role=tab]').count(), 5);
    assert.equal(await page.locator('#solo-tab-round').isVisible(), true);
    assert.equal(await page.locator('#solo-tab-journal').isVisible(), false);
    assert.equal(await page.locator('#solo-tab-round #case-journal').count(), 0);
    assert.equal(await page.locator('#solo-tab-journal #influence-target').count(), 0);
    await click(page, '#solo-proceed');
    await click(page, '#solo-proceed');
    assert.equal(await page.evaluate(() => state.night_step), 'detective');
    const guidance = await page.evaluate(() => state.scenario.tutorial_guidance);
    assert.ok(guidance.question_target && guidance.suspect_target);
    await page.locator(`[data-player="${guidance.suspect_target}"]`).click();
    assert.equal(await page.evaluate(() => state.pick), null, 'Selecting is not confirming');
    await click(page, '#confirm-action');
    assert.ok(await page.evaluate(() => state.notes.length));
    await dismiss(page);
    await click(page, '#solo-proceed');
    await dismiss(page);
    assert.equal(await page.evaluate(() => state.phase), 'day');
    assert.match(await page.locator('#practice-guide').textContent(), /Mara/);

    // A real server action is held in flight to check pending and accepted feedback.
    await tab(page, 'influence');
    let release, captured;
    const gate = new Promise(resolve => { release = resolve; });
    const received = new Promise(resolve => { captured = resolve; });
    await page.route('**/api/solo-influence', async route => {
      const response = await route.fetch(); captured(); await gate; await route.fulfill({response});
    }, {times:1});
    await page.locator('[data-solo-stance="suspect"]').click();
    await received;
    assert.equal(await page.locator('#case-influence').getAttribute('aria-busy'), 'true');
    assert.match(await page.locator('#influence-feedback').textContent(), /Submitting/);
    release();
    await page.waitForFunction(() => !busy);
    assert.match(await page.locator('#influence-feedback').textContent(), /Accepted/);
    assert.equal(await page.evaluate(() => influenceFeedback.changed_witnesses.length), 0);
    assert.match(await page.locator('#influence-feedback').textContent(), /No witness/);
    await click(page, '[data-solo-stance="suspect"]');
    assert.match(await page.locator('#influence-feedback').textContent(), /Already recorded/);
    await page.evaluate(() => run('solo-influence', {target:'missing-witness',stance:'suspect'}));
    assert.match(await page.locator('#influence-feedback').textContent(), /Rejected.*Choose a living witness/s);
    await page.evaluate(() => poll(true));
    assert.match(await page.locator('#influence-feedback').textContent(), /Rejected/);
    await click(page, '[data-solo-stance="neutral"]');

    await tab(page, 'journal');
    assert.ok(await page.locator('#round-accounts .journal-entry').count());
    await tab(page, 'round');
    await page.locator('#question-target').selectOption(guidance.question_target);
    await click(page, '[data-solo-question="detail"]');
    assert.equal(await page.evaluate(() => state.scenario.interrogation.used), true);
    assert.equal(await page.locator('[data-solo-question]:enabled').count(), 0);
    await tab(page, 'journal');
    await click(page, '#inspect-scene');
    await click(page, '#compare-accounts');
    assert.ok(await page.evaluate(() => state.scenario.journal.some(entry => entry.id === 'dispatch-log')));
    assert.ok(await page.evaluate(() => state.scenario.connections.some(entry => entry.id === 'dispatch-route')));
    assert.ok(await page.locator('#case-journal').textContent().then(text => text.includes('Revised statement')));
    await tab(page, 'influence');
    await page.locator('#influence-target').selectOption(guidance.suspect_target);
    await click(page, '[data-solo-stance="suspect"]');
    const effect = await page.evaluate(() => influenceFeedback);
    assert.ok(effect.changed_witnesses.length > 0);
    for (const name of effect.changed_witnesses) assert.ok((await page.locator('#influence-feedback').textContent()).includes(name));
    await page.reload();
    await page.waitForFunction(() => state?.phase === 'day');
    await tab(page, 'influence');
    assert.deepEqual(await page.evaluate(() => influenceFeedback.changed_witnesses), effect.changed_witnesses);

    for (const width of [320,390,1440]) {
      await page.setViewportSize({width,height:900});
      for (const name of ['round','journal','dossier','influence','chat']) {
        await tab(page, name);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} overflows at ${width}`);
        if ((width === 320 && ['journal','influence'].includes(name)) || (width === 390 && name === 'round') || (width === 1440 && name === 'influence')) {
          await page.locator(`#solo-tab-${name}`).evaluate(el => el.scrollIntoView({block:'start',behavior:'instant'}));
          await page.screenshot({path:`/tmp/mafia-features-${name}-${width}.png`});
        }
      }
    }
    await page.locator('#tab-round').focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#tab-journal').getAttribute('aria-selected'), 'true');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'tab-journal');
    await tab(page, 'round');
    await click(page, '#proceed-vote');
    await tab(page, 'influence');
    assert.equal(await page.locator('[data-solo-stance]:enabled').count(), 0);
    await tab(page, 'round');
    await page.locator(`[data-player="${guidance.suspect_target}"]`).click();
    await click(page, '#confirm-action');
    await dismiss(page);
    assert.equal(await page.evaluate(() => state.phase), 'over');
    assert.equal(await page.evaluate(() => state.winner), 'town');
    assert.equal(await page.evaluate(() => state.players.find(person => person.you).score), 0);
    assert.match(await page.locator('#practice-guide').textContent(), /Practice complete/);

    // Private teammate messages arrive while their panel is hidden, with durable seq-based unread tracking.
    const lead = await post('solo', {name:'Notification Lead',scenario_id:'ninth-photograph'}); identities.push(lead);
    await page.evaluate(identity => { localStorage.setItem('mafia', JSON.stringify({code:identity.code,pid:identity.pid})); }, lead);
    await page.reload();
    await page.waitForFunction(() => state?.phase === 'lobby' && !state.tutorial);
    const invitation = await page.evaluate(() => state.team.invite_path);
    const params = new URL(invitation, base).searchParams;
    const friend = await post('solo-join', {code:lead.code,invite:params.get('invite'),name:'Notification Friend'});
    await click(page, '#start');
    await page.evaluate(() => {
      window.notificationCalls = [];
      window.originalToast = toast;
      toast = message => { notificationCalls.push(message); originalToast(message); };
    });
    await post('team-chat', {...friend,text:'A fresh private clue'});
    await page.evaluate(() => poll(true));
    assert.equal(await page.locator('#tab-chat .unread-badge').textContent(), '1');
    assert.match(await page.locator('#tab-chat').getAttribute('aria-label'), /1 unread teammate message/);
    assert.equal(await page.locator('#toast').getAttribute('aria-live'), 'polite');
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'/tmp/mafia-features-chat-unread-390.png'});
    assert.equal(await page.evaluate(() => notificationCalls.filter(text => text.includes('fresh private clue')).length), 1);
    await page.evaluate(() => poll(true));
    assert.equal(await page.evaluate(() => notificationCalls.filter(text => text.includes('fresh private clue')).length), 1);
    await post('team-chat', {...lead,text:'My own plan'});
    await page.evaluate(() => poll(true));
    assert.equal(await page.locator('#tab-chat .unread-badge').textContent(), '1');
    assert.equal(await page.evaluate(() => notificationCalls.some(text => text.includes('My own plan'))), false);
    await page.reload();
    await page.waitForFunction(() => state?.phase === 'night');
    assert.equal(await page.locator('#tab-chat .unread-badge').textContent(), '1');
    assert.ok(!(await page.locator('#toast').textContent()).includes('fresh private clue'));
    await tab(page, 'chat');
    if (!(await page.locator('#team-panel').evaluate(el => el.open))) await page.locator('#team-panel summary').click();
    await page.locator('#messages-team').scrollIntoViewIfNeeded();
    await page.waitForFunction(() => unreadChatCount() === 0);
    assert.equal(await page.locator('#tab-chat .unread-badge').count(), 0);
    await post('team-chat', {...friend,text:'Read while the panel is visible'});
    await page.evaluate(() => poll(true));
    assert.equal(await page.locator('#tab-chat .unread-badge').count(), 0);
    await page.reload();
    await page.waitForFunction(() => state?.phase === 'night');
    assert.equal(await page.locator('#tab-chat .unread-badge').count(), 0);
    await post('end', lead);
    await page.evaluate(() => poll(true));
    await dismiss(page);
    await click(page, '#new-case');
    await page.locator('#story-choice').selectOption('room-kept-warm');
    await click(page, '#confirm-next-case');
    assert.equal(await page.evaluate(() => state.phase), 'lobby');
    assert.equal(await page.evaluate(() => session.code), lead.code);
    assert.equal(await page.evaluate(() => state.team.count), 1);
    assert.equal((await post('state', friend)).phase, 'lobby');
    assert.equal(await page.evaluate(() => state.team_chat.some(message => message.t.includes('fresh private clue'))), true);
    assert.deepEqual(errors, []);
    console.log('Gameplay features passed: real guided practice and ballot, five distinct responsive keyboard tabs, truthful pending/accepted/unchanged/rejected influence with real preference changes, durable private chat unread notifications, and next-case team continuity.');
  } finally {
    for (const identity of identities) await post('leave', identity).catch(() => {});
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
