const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body) {
  const r = await fetch(base + '/api/' + route, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const data = await r.json(); assert.equal(r.status, 200, JSON.stringify(data)); return data;
}
(async () => {
 const browser = await chromium.launch({executablePath:'/usr/bin/chromium', headless:true, args:['--no-sandbox']});
 let identity;
 try {
  const page = await browser.newPage({viewport:{width:390,height:844}}), errors=[];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base);
  await page.getByRole('button',{name:'Online play',exact:false}).waitFor();
  await page.getByRole('button',{name:'Solo run',exact:false}).waitFor();
  await page.screenshot({path:'/tmp/mafia-modes.png'});
  await page.locator('#solo-run').click();
  await page.locator('#name').fill('Case Reader');
  await page.locator('#entry button[type=submit]').click();
  await page.waitForFunction(() => state?.mode === 'solo' && state.phase === 'lobby');
  identity = await page.evaluate(() => session);
  const firstCase = await page.evaluate(() => state.scenario.id);
  assert.equal(await page.locator('.case-person').count(),6);
  assert.equal(await page.evaluate(() => state.settings.mafia_count),1);
  assert.equal(await page.locator('#clock').count(),0);
  for (const width of [390,1440]) {
   await page.setViewportSize({width,height:900});
   assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  }
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'/tmp/mafia-solo-briefing.png',fullPage:true});
  await page.reload();
  await page.waitForFunction(() => state?.phase === 'lobby');
  assert.equal(await page.evaluate(() => state.scenario.id),firstCase);
  await page.locator('#start').click();
  await page.waitForFunction(() => state?.night_step === 'detective');
  assert.equal(await page.evaluate(() => state.me.role),'detective');
  const target = await page.evaluate(() => state.players.find(p => !p.you && p.alive).id);
  await page.locator(`[data-player="${target}"]`).click();
  await page.locator('#confirm-action').click();
  await page.locator('#investigation-dialog[open]').waitFor();
  await page.locator('#dismiss-investigation').click();
  if (await page.locator('#death-notice').evaluate(e => e.open)) await page.locator('#dismiss-death').click();
  await page.waitForFunction(() => state?.phase === 'day' && state.me.alive);
  const npc = await page.evaluate(() => state.scenario.cast.find(c => state.players.find(p => p.id === c.id).alive));
  await page.locator('#input-town').fill(`@${npc.name}, where were you before the first alarm?`);
  await page.locator('.composer[data-channel=town] button').click();
  await page.waitForFunction(name => state.scenario.journal.some(e => e.source === name && e.kind === 'account'),npc.name);
  await page.waitForFunction(() => !busy);
  await page.waitForTimeout(900); // Respect the public-chat rate limit between questions.
  await page.locator('#case-journal > summary').click();
  await page.getByRole('button',{name:'Inspect the scene',exact:true}).click();
  await page.waitForFunction(() => state.scenario.journal.some(e=>e.kind==='document'));
  assert.equal(await page.locator('#case-solution').count(),0);
  await page.locator('#case-dossier').click();
  assert.equal(await page.locator('#case-dossier').evaluate(e => e.open),true);
  await page.screenshot({path:'/tmp/mafia-solo-play.png',fullPage:true});
  await post('end',identity);
  await page.waitForFunction(() => state?.phase === 'over');
  await page.getByRole('heading',{name:'The final account'}).waitFor();
  await page.locator('#new-case').click();
  await page.locator('#entry button[type=submit]').click();
  await page.waitForFunction(() => state?.mode === 'solo' && state.phase === 'lobby');
  assert.notEqual(await page.evaluate(() => state.scenario.id),firstCase);
  await page.locator('#leave').click();
  await page.locator('#online-play').click();
  await page.locator('#entry button[type=submit]').click();
  await page.waitForFunction(() => state?.mode === 'online' && state.phase === 'lobby');
  assert.equal(await page.evaluate(() => state.scenario),null);
  await page.locator('#leave').click();
  assert.deepEqual(errors,[]);
  console.log('Solo browser checks passed: mode choice, paused case, cast, reload, mobile/desktop, Detective turn, contextual interview, ending, new case and online play.');
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1});
