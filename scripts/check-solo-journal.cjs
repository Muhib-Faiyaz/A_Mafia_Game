const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const cases = require('../data/solo_scenarios.json');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body) {
  const response = await fetch(base + '/api/' + route, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  assert.equal(response.status,200,data.error || 'Unexpected API response');
  return data;
}
async function dismiss(page) {
  for (let i=0;i<8;i++) {
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
  page.on('pageerror',e=>errors.push(e.message));
  identity=await post('solo',{name:'Journal Reader'});
  await page.addInitScript(s=>localStorage.setItem('mafia',JSON.stringify(s)),identity);
  await post('start',identity);
  await page.goto(base);
  await page.waitForFunction(()=>state?.night_step==='detective');
  const caseId=await page.evaluate(()=>state.scenario.id), canon=cases.find(c=>c.id===caseId);
  const doctorName=canon.cast.find(c=>c.key===canon.doctor).name;
  const target=await page.evaluate(name=>state.players.find(p=>p.name===name).id,doctorName);
  await post('act',{...identity,target});
  await page.waitForFunction(()=>state?.phase==='day');
  await dismiss(page);
  await page.locator('#case-journal > summary').click();
  await page.getByRole('button',{name:'Inspect the scene',exact:true}).click();
  await page.waitForFunction(()=>state.scenario.journal.some(e=>e.kind==='document'));
  await page.waitForFunction(()=>!busy);
  await page.waitForTimeout(900);
  await page.getByRole('button',{name:'Inspect the scene',exact:true}).click();
  await page.waitForFunction(()=>state.scenario.journal.filter(e=>e.kind==='document').length===2);
  const npc=await page.evaluate(()=>state.scenario.cast.find(c=>c.alive));
  const interview=page.locator('.case-interview').filter({has:page.locator('summary',{hasText:npc.name})});
  await interview.locator('summary').click();
  await page.waitForTimeout(900);
  await interview.getByRole('button',{name:'Ask what they noticed',exact:true}).click();
  await page.waitForFunction(name=>state.scenario.journal.some(e=>e.source===name && e.kind==='observation'),npc.name);
  await page.waitForFunction(()=>!busy);
  assert.equal(await interview.evaluate(el=>el.open),true);
  const before=await page.evaluate(name=>state.chat.filter(c=>c.n===name && c.k==='msg').map(c=>c.t),npc.name);
  await page.waitForTimeout(900);
  await interview.getByRole('button',{name:'Ask what they noticed',exact:true}).click();
  await page.waitForFunction(()=>!busy);
  const after=await page.evaluate(name=>state.chat.filter(c=>c.n===name && c.k==='msg').map(c=>c.t),npc.name);
  assert.equal(new Set(after).size,after.length);
  assert.ok(after.length>=before.length);
  for(const width of [320,390,1440]) {
    await page.setViewportSize({width,height:900});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.setViewportSize({width:390,height:844});
  await page.locator('#case-journal').scrollIntoViewIfNeeded();
  await page.screenshot({path:'/tmp/mafia-seven-case-journal.png'});
  const entries=await page.evaluate(()=>state.scenario.journal.length);
  await page.reload();
  await page.waitForFunction(count=>state?.scenario.journal.length>=count,entries);
  assert.equal(await page.locator('#case-solution').count(),0);
  // Drive a real inquiry through the public chat API, respecting its rate limit.
  for(const character of canon.cast) {
    for(const text of [`@${character.name}, what is your account?`,`@${character.name}, what did you notice?`]) {
      await page.waitForTimeout(850);
      await post('chat',{...identity,text});
    }
  }
  const current=await post('state',identity);
  for(const character of current.scenario.cast.filter(c=>c.alive)) {
    await page.waitForTimeout(850);
    await post('chat',{...identity,text:`I trust ${character.name}`});
    await page.waitForTimeout(850);
    await post('chat',{...identity,text:`@${character.name}, what are you hiding?`});
  }
  const culpritName=canon.cast.find(c=>c.key===canon.culprit).name;
  await page.waitForTimeout(850);
  await post('chat',{...identity,text:`I suspect ${culpritName}`});
  const collected=await post('state',identity);
  assert.ok(collected.scenario.connections.length>=2);
  const speeches=collected.chat.filter(c=>c.k==='msg' && c.n!=='Journal Reader').map(c=>c.t);
  assert.equal(new Set(speeches).size,speeches.length);
  assert.ok(!speeches.some(t=>t.includes('I lean towards')));
  await post('proceed',identity);
  await post('vote',{...identity,target:collected.players.find(p=>p.name===culpritName).id});
  await page.waitForFunction(()=>state?.phase==='over');
  assert.equal(await page.evaluate(()=>state.winner),'town');
  await dismiss(page);
  await page.locator('#case-solution > summary').click();
  assert.equal(await page.evaluate(()=>state.scenario.solution),canon.solution);
  assert.equal(await page.locator('#case-solution li').count(),canon.timeline.length);
  assert.equal(await page.evaluate(()=>state.players.filter(p=>p.role==='mafia').length),1);
  assert.deepEqual(errors,[]);
  console.log('Solo journal browser checks passed: inspections, persistent interviews, unique testimony, reload, mobile/desktop, public inquiry, evidence-led vote and case solution.');
 } finally {
  if(identity) await post('leave',identity).catch(()=>{});
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
