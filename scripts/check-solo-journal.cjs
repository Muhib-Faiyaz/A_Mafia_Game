const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body, status=200) {
  const response=await fetch(base+'/api/'+route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json(); assert.equal(response.status,status,data.error||'Unexpected API response'); return data;
}
async function click(page,selector) {
  await page.waitForFunction(()=>!busy); await page.locator(selector).click(); await page.waitForFunction(()=>!busy);
}
async function dismiss(page) {
  for(let i=0;i<12;i++) {
    if(await page.locator('#investigation-dialog').evaluate(el=>el.open)) await page.locator('#dismiss-investigation').click();
    else if(await page.locator('#death-notice').evaluate(el=>el.open)) await page.locator('#dismiss-death').click();
    else break;
  }
}
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 let identity;
 try {
  const catalog=await fetch(base+'/api/stories').then(r=>r.json());
  identity=await post('solo',{name:'Journal Reader',scenario_id:catalog.stories[0].id});
  await post('start',identity);
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(s=>localStorage.setItem('mafia',JSON.stringify(s)),identity);
  await page.goto(base);
  await page.waitForFunction(()=>state?.night_step==='mafia');
  assert.equal(await page.locator('#clock, #progress').count(),0);
  // Reading and polling cannot advance the solo night.
  for(let i=0;i<4;i++) assert.equal((await post('state',identity)).night_step,'mafia');
  await click(page,'#solo-proceed');
  await click(page,'#solo-proceed');
  assert.equal(await page.evaluate(()=>state.night_step),'detective');
  await click(page,'#solo-proceed'); // Explicitly skip investigation.
  await dismiss(page);
  assert.equal(await page.evaluate(()=>state.phase),'day');
  const first=await post('state',identity);
  for(const witness of first.scenario.cast.filter(p=>p.alive)) {
    assert.equal(first.chat.filter(c=>c.n===witness.name && c.t===witness.statement).length,1);
  }
  const speeches=first.chat.filter(c=>c.k==='msg').map(c=>c.t);
  for(let i=0;i<5;i++) await post('state',identity);
  assert.deepEqual((await post('state',identity)).chat.filter(c=>c.k==='msg').map(c=>c.t),speeches);
  await click(page,'#nav [data-solo-tab="journal"]');
  await click(page,'#inspect-scene');
  await page.waitForFunction(()=>state.scenario.journal.some(e=>e.kind==='document'));
  await click(page,'#compare-accounts');
  assert.equal(await page.evaluate(()=>state.scenario.interrogation.used),false);
  await click(page,'#nav [data-solo-tab="round"]');
  const witness=await page.evaluate(()=>state.scenario.cast.find(p=>p.alive && p.question_options.some(q=>q.id==='correction' && q.available)));
  const original=witness.statement;
  await page.locator('#question-target').selectOption(witness.id);
  assert.equal(await page.locator('[data-solo-question]').count(),3);
  await click(page,'[data-solo-question="correction"]');
  await page.waitForFunction(()=>state.scenario.interrogation.used && state.scenario.revisions.length===1);
  assert.notEqual(await page.evaluate(id=>state.scenario.cast.find(p=>p.id===id).statement,witness.id),original);
  assert.equal(await page.locator('[data-solo-question]:enabled').count(),0);
  assert.equal(await page.locator('#question-target').isDisabled(),true);
  assert.match(await page.locator('#question-count').textContent(),new RegExp(witness.name));
  const other=await page.evaluate(id=>state.scenario.cast.find(p=>p.alive && p.id!==id).id,witness.id);
  await post('solo-question',{...identity,target:other,question:'motive'},400);
  await post('chat',{...identity,text:`@${witness.name}, another question?`},400);
  await click(page,'#nav [data-solo-tab="influence"]');
  await page.locator('#influence-target').selectOption(witness.id);
  await click(page,'[data-solo-stance="suspect"]');
  await page.waitForFunction(name=>state.chat.some(c=>c.t.includes('case against '+name)),witness.name);
  await click(page,'[data-solo-stance="defend"]');
  await page.waitForFunction(name=>state.chat.some(c=>c.t.includes('defense of '+name)),witness.name);
  await click(page,'[data-solo-stance="neutral"]');
  assert.equal(await page.evaluate(()=>state.scenario.revisions.length),1);
  const entries=await page.evaluate(()=>state.scenario.journal.length);
  await page.reload();
  await page.waitForFunction(count=>state?.scenario.journal.length>=count && state.scenario.interrogation.used,entries);
  await click(page,'#nav [data-solo-tab="round"]');
  assert.equal(await page.locator('[data-solo-question]:enabled').count(),0);
  assert.equal(await page.locator('#input-town').count(),0);
  for(const width of [320,390,1440]) {
    await page.setViewportSize({width,height:900});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.setViewportSize({width:390,height:844});
  await click(page,'#nav [data-solo-tab="journal"]');
  await page.locator('#case-journal').scrollIntoViewIfNeeded();
  await page.screenshot({path:'/tmp/mafia-structured-solo-journal.png'});
  await page.locator('#nav [data-solo-tab="chat"]').click();
  assert.equal(await page.locator('#solo-tab-chat').isVisible(),true);
  assert.equal(await page.locator('.composer[data-channel=town]').count(),0);
  await post('end',identity);
  await page.waitForFunction(()=>state?.phase==='over');
  await dismiss(page);
  assert.equal(await page.locator('#solo-tab-dossier').isVisible(),true);
  assert.ok((await page.locator('#case-reconstruction p').count())>0);
  assert.ok((await page.locator('#case-solution li').count())>0);
  assert.deepEqual(errors,[]);
  console.log('Solo journal browser checks passed: manual progression, single round accounts, one selected question/revision, cross-bot quota enforcement, structured persuasion, reload, responsive tabs and full reconstruction.');
 } finally {
  if(identity) await post('leave',identity).catch(()=>{});
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
