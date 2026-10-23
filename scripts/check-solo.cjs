const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body) {
  const response = await fetch(base + '/api/' + route, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  assert.equal(response.status,200,data.error || 'Unexpected response');
  return data;
}
async function click(page, selector) {
  await page.waitForFunction(() => !busy);
  await page.locator(selector).click();
  await page.waitForFunction(() => !busy);
}
async function dismiss(page) {
  for (let i=0;i<12;i++) {
    if (await page.locator('#investigation-dialog').evaluate(el=>el.open)) await page.locator('#dismiss-investigation').click();
    else if (await page.locator('#death-notice').evaluate(el=>el.open)) await page.locator('#dismiss-death').click();
    else break;
  }
}
(async()=>{
 const browser = await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 let identity;
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}}), errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(base);
  await page.locator('#online-play').waitFor();
  await page.locator('#solo-run').click();
  await page.waitForFunction(()=>storyCatalog.length===7);
  assert.equal(await page.locator('#story-choice option').count(),8);
  await page.locator('#story-list > summary').click();
  assert.equal(await page.locator('.story-catalog li').count(),7);
  assert.match(await page.locator('#story-list').textContent(),/story[- ]skills/i);
  const chosen=await page.evaluate(()=>storyCatalog[0]);
  await page.locator('#story-choice').selectOption(chosen.id);
  await page.locator('#name').fill('Case Reader');
  await click(page,'#entry button[type=submit]');
  identity=await page.evaluate(()=>session);
  assert.equal(await page.evaluate(()=>state.scenario.id),chosen.id);
  assert.equal(await page.evaluate(()=>state.settings.mafia_count),1);
  assert.equal(await page.locator('.case-person').count(),6);
  assert.match(await page.locator('.story-origin').first().textContent(),/Writing source:/);
  await page.reload();
  await page.waitForFunction(id=>state?.scenario.id===id,chosen.id);
  await click(page,'#start');
  assert.equal(await page.evaluate(()=>state.night_step),'mafia');
  assert.equal(await page.evaluate(()=>state.timer_total),0);
  assert.equal(await page.locator('#clock, #progress').count(),0);
  await click(page,'#solo-proceed');
  assert.equal(await page.evaluate(()=>state.night_step),'doctor');
  await click(page,'#solo-proceed');
  assert.equal(await page.evaluate(()=>state.night_step),'detective');
  const target=await page.evaluate(()=>state.players.find(p=>!p.you && p.alive).id);
  await page.locator(`[data-player="${target}"]`).click();
  await click(page,'#confirm-action');
  await page.locator('#investigation-dialog[open]').waitFor();
  assert.equal(await page.evaluate(()=>state.night_step),'detective');
  await dismiss(page);
  await click(page,'#solo-proceed');
  await dismiss(page);
  assert.equal(await page.evaluate(()=>state.phase),'day');
  assert.equal(await page.locator('#input-town').count(),0);
  assert.deepEqual(await page.locator('#nav [data-solo-tab]').evaluateAll(els=>els.map(el=>el.dataset.soloTab)),['round','journal','dossier','influence','chat']);
  for (const tab of ['round','journal','dossier','influence','chat']) {
    await page.locator(`#nav [data-solo-tab="${tab}"]`).click();
    assert.equal(await page.locator(`#solo-tab-${tab}`).isVisible(),true);
  }
  await page.locator('#nav [data-solo-tab="round"]').click();
  await page.locator('.solo-tab-help > summary').click();
  assert.match(await page.locator('.solo-tab-help').textContent(),/Type privately/);
  await page.locator('#nav [data-solo-tab="influence"]').click();
  await page.locator('#solo-voting-help > summary').click();
  assert.match(await page.locator('#solo-voting-help').textContent(),/unsupported accusation alone is not enough/);
  for(const width of [320,390,1440]) {
    await page.setViewportSize({width,height:900});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'/tmp/mafia-selected-story.png'});
  await post('end',identity);
  await page.waitForFunction(()=>state?.phase==='over');
  await dismiss(page);
  assert.equal(await page.locator('#solo-tab-dossier').isVisible(),true);
  assert.ok((await page.locator('#case-reconstruction p').count())>0);
  assert.ok((await page.locator('#case-solution li').count())>0);
  await click(page,'#new-case');
  await page.waitForFunction(()=>storyCatalog.length===7);
  const previousIdentity={...identity};
  await page.locator('#next-case-picker #story-choice').selectOption('random');
  await click(page,'#confirm-next-case');
  identity=await page.evaluate(()=>session);
  assert.deepEqual(identity,previousIdentity);
  assert.notEqual(await page.evaluate(()=>state.scenario.id),chosen.id);
  await click(page,'#leave'); identity=null;
  await page.locator('#online-play').click();
  await page.locator('#name').fill('Online Reader');
  await click(page,'#entry button[type=submit]');
  identity=await page.evaluate(()=>session);
  assert.equal(await page.evaluate(()=>state.mode),'online');
  assert.equal(await page.evaluate(()=>state.scenario),null);
  await click(page,'#leave'); identity=null;
  assert.deepEqual(errors,[]);
  console.log('Solo browser checks passed: story picker/random/provenance, paused briefing, manual night turns, investigation, solo tabs/help, mobile layouts, full ending and online play.');
 } finally {
  if(identity) await post('leave',identity).catch(()=>{});
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
