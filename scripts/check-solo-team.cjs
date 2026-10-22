const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body, status=200) {
  const response = await fetch(base + '/api/' + route, {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body),
  });
  const data = await response.json();
  assert.equal(response.status, status, data.error || 'Unexpected response');
  return data;
}
async function dismiss(page) {
  for (let i=0; i<12; i++) {
    if (await page.locator('#investigation-dialog').evaluate(e => e.open)) await page.locator('#dismiss-investigation').click();
    else if (await page.locator('#death-notice').evaluate(e => e.open)) await page.locator('#dismiss-death').click();
    else break;
  }
}
(async () => {
 const browser = await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 let lead;
 try {
  const errors=[], pages=[];
  for (let i=0;i<4;i++) {
   const context = await browser.newContext({viewport:{width:390,height:844}});
   const page = await context.newPage();
   page.on('pageerror', error => errors.push(error.message));
   pages.push(page);
  }
  const [host, one, two, extra] = pages;
  await host.goto(base);
  await host.locator('#solo-run').click();
  await host.locator('#name').fill('Lead Reader');
  await host.locator('#entry button[type=submit]').click();
  await host.waitForFunction(() => state?.mode === 'solo');
  lead = await host.evaluate(() => session);
  await host.locator('#team-panel summary').click();
  const invitation = await host.locator('#solo-invite-link').inputValue();
  for (const [page, name] of [[one,'Ally One'], [two,'Ally Two']]) {
   await page.goto(invitation);
   await page.locator('#friend-name').fill(name);
   await page.locator('#invite-entry button[type=submit]').click();
   await page.waitForFunction(() => state?.me.friend);
   assert.equal(new URL(page.url()).search,'');
   assert.equal(await page.locator('#start').count(),0);
   assert.equal(await page.locator('#solo-invite-link').count(),0);
   assert.equal(await page.evaluate(() => state.players.length),7);
  }
  await host.waitForFunction(() => state?.team.count === 2);
  assert.equal(await host.locator('#copy-solo-invite').isDisabled(),true);
  await extra.goto(invitation);
  await extra.locator('#friend-name').fill('Third Friend');
  await extra.locator('#invite-entry button[type=submit]').click();
  await extra.waitForFunction(() => document.querySelector('#toast').textContent.includes('team is full'));
  assert.equal(await extra.evaluate(() => session),null);
  await one.locator('#input-team').fill('Keep our evidence here <b>only</b>');
  await one.locator('.composer[data-channel=team] button').click();
  await Promise.all([host,two].map(page => page.waitForFunction(() => state.team_chat.some(m => m.t.includes('<b>only</b>')))));
  assert.equal(await host.locator('#messages-team b').filter({hasText:'only'}).count(),0);
  assert.equal(await host.locator('#messages-team').textContent().then(t=>t.includes('<b>only</b>')),true);
  assert.equal(await host.evaluate(() => state.chat.some(m=>m.t.includes('Keep our evidence'))),false);
  for (const page of [host,one]) {
   for (const width of [390,1440]) {
    await page.setViewportSize({width,height:900});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
   }
   await page.setViewportSize({width:390,height:844});
  }
  await host.screenshot({path:'/tmp/mafia-solo-team.png',fullPage:true});
  await one.reload();
  await one.waitForFunction(() => state?.team?.count === 2 && state.me.friend);
  assert.equal(await one.locator('#messages-team').textContent().then(t=>t.includes('Keep our evidence')),true);
  await host.locator('#start').click();
  await one.waitForFunction(() => state?.night_step === 'detective');
  const target = await one.evaluate(() => state.players.find(p=>!p.you && p.alive).id);
  await one.locator(`[data-player="${target}"]`).click();
  await one.locator('#confirm-action').click();
  await Promise.all([host,one,two].map(page=>page.locator('#investigation-dialog[open]').waitFor()));
  const results = await Promise.all([host,one,two].map(page=>page.locator('#investigation-result').textContent()));
  assert.equal(new Set(results).size,1);
  for (const page of [host,one,two]) await dismiss(page);
  await one.waitForFunction(() => state?.phase === 'day');
  await dismiss(one);
  assert.equal(await one.locator('#input-town').count(),0);
  assert.equal(await host.locator('#input-town').count(),1);
  await one.locator('#proceed-vote').click();
  await host.waitForFunction(() => state?.discussion.voted);
  assert.equal(await host.evaluate(() => state.voting || state.discussion.voted),true);
  assert.equal(await two.evaluate(() => state.players.filter(p=>p.you).length),1);
  for (const page of [host,one,two]) {
   assert.equal(await page.evaluate(() => state.me.alive),true);
   assert.equal(await page.evaluate(() => state.players.find(p=>p.you).protected),true);
  }
  await two.locator('#leave-solo-friend').click();
  await host.waitForFunction(() => state?.team.count === 1);
  assert.equal(await host.locator('#copy-solo-invite').isEnabled(),true);
  await extra.locator('#invite-entry button[type=submit]').click();
  await extra.waitForFunction(() => state?.me.friend);
  assert.equal(await extra.evaluate(() => state.phase),'day');
  await extra.reload();
  await extra.waitForFunction(() => state?.me.friend && state.me.alive);
  await one.waitForFunction(() => state?.voting);
  const day = await one.evaluate(() => state.day);
  await dismiss(one);
  await one.locator('#skip-vote').click();
  await one.locator('#confirm-action').click();
  await one.waitForFunction(previousDay => state.phase === 'over' || state.day > previousDay, day);
  await host.waitForFunction(previousDay => state.phase === 'over' || state.day > previousDay, day);
  assert.equal(await host.evaluate(() => state.me.alive),true);
  // The host's ordinary leave action closes the shared case for every teammate.
  await post('leave',lead); lead=null;
  for (const page of [one,extra]) await page.waitForFunction(() => session === null);
  assert.deepEqual(errors,[]);
  console.log('Solo team browser checks passed: private invites, two-friend cap, shared investigation/readiness/ballot, isolated chat, reloads, mobile/desktop, late joins, leaving and room closure.');
 } finally {
  if (lead) await post('leave',lead).catch(()=>{});
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1});
