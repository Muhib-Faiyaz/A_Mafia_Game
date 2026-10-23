const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body, status=200) {
  const response=await fetch(base+'/api/'+route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json(); assert.equal(response.status,status,data.error||'Unexpected response'); return data;
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
 let lead;
 try {
  const pages=[],errors=[];
  for(let i=0;i<4;i++) {
    const context=await browser.newContext({viewport:{width:390,height:844}}), page=await context.newPage();
    page.on('pageerror',error=>errors.push(error.message)); pages.push(page);
  }
  const [host,one,two,extra]=pages;
  await host.goto(base);
  await host.locator('#solo-run').click();
  await host.waitForFunction(()=>storyCatalog.length===7);
  await host.locator('#name').fill('Lead Reader');
  await click(host,'#entry button[type=submit]');
  lead=await host.evaluate(()=>session);
  await host.locator('#team-panel summary').click();
  const invitation=await host.locator('#solo-invite-link').inputValue();
  for(const [page,name] of [[one,'Ally One'],[two,'Ally Two']]) {
    await page.goto(invitation);
    await page.locator('#friend-name').fill(name);
    await click(page,'#invite-entry button[type=submit]');
    await page.waitForFunction(()=>state?.me.friend);
    assert.equal(new URL(page.url()).search,'');
    assert.equal(await page.locator('#start').count(),0);
    assert.equal(await page.locator('#solo-invite-link').count(),0);
    assert.equal(await page.evaluate(()=>state.players.length),7);
  }
  await host.waitForFunction(()=>state.team.count===2);
  assert.equal(await host.locator('#copy-solo-invite').isDisabled(),true);
  await extra.goto(invitation);
  await extra.locator('#friend-name').fill('Third Friend');
  await click(extra,'#invite-entry button[type=submit]');
  await extra.waitForFunction(()=>document.querySelector('#toast').textContent.includes('team is full'));
  assert.equal(await extra.evaluate(()=>session),null);
  await one.locator('#input-team').fill('Keep our evidence here <b>only</b>');
  await click(one,'.composer[data-channel=team] button');
  await Promise.all([host,two].map(page=>page.waitForFunction(()=>state.team_chat.some(m=>m.t.includes('<b>only</b>')))));
  assert.equal(await host.locator('#messages-team b').filter({hasText:'only'}).count(),0);
  assert.equal(await host.evaluate(()=>state.chat.some(m=>m.t.includes('Keep our evidence'))),false);
  await one.reload();
  await one.waitForFunction(()=>state?.team.count===2 && state.me.friend);
  assert.match(await one.locator('#messages-team').textContent(),/Keep our evidence/);
  await click(host,'#start');
  await one.waitForFunction(()=>state?.night_step==='mafia');
  await click(host,'#solo-proceed');
  await click(host,'#solo-proceed');
  await one.waitForFunction(()=>state?.night_step==='detective');
  const target=await one.evaluate(()=>state.players.find(p=>!p.you && p.alive).id);
  await one.locator(`[data-player="${target}"]`).click();
  await click(one,'#confirm-action');
  await Promise.all([host,one,two].map(page=>page.locator('#investigation-dialog[open]').waitFor()));
  const results=await Promise.all([host,one,two].map(page=>page.locator('#investigation-result').textContent()));
  assert.equal(new Set(results).size,1);
  for(const page of [host,one,two]) await dismiss(page);
  assert.equal(await one.evaluate(()=>state.night_step),'detective');
  await click(host,'#solo-proceed');
  await Promise.all([host,one,two].map(page=>page.waitForFunction(()=>state?.phase==='day')));
  for(const page of [host,one,two]) await dismiss(page);
  assert.equal(await host.locator('#input-town').count(),0);
  assert.equal(await one.locator('#input-town').count(),0);
  const witness=await one.evaluate(()=>state.scenario.cast.find(p=>p.alive && p.question_options.some(q=>q.id==='correction' && q.available)));
  await one.locator('#question-target').selectOption(witness.id);
  await click(one,'[data-solo-question="correction"]');
  await Promise.all([host,two].map(page=>page.waitForFunction(()=>state.scenario.interrogation.used)));
  for(const page of [host,one,two]) {
    assert.equal(await page.locator('[data-solo-question]:enabled').count(),0);
    assert.match(await page.locator('#question-count').textContent(),/Question used/);
  }
  const another=await host.evaluate(id=>state.scenario.cast.find(p=>p.alive && p.id!==id).id,witness.id);
  await post('solo-question',{...lead,target:another,question:'motive'},400);
  const ally=await one.evaluate(()=>session);
  await post('chat',{...lead,text:'A typed question?'} ,400);
  await click(one,'#proceed-vote');
  await host.waitForFunction(()=>state.voting && state.discussion.voted);
  assert.equal(await host.evaluate(()=>state.players.filter(p=>p.you).length),1);
  await click(one,'#skip-vote');
  await click(one,'#confirm-action');
  await host.waitForFunction(()=>state.phase==='night' && state.day===2);
  assert.equal(await host.evaluate(()=>state.scenario.interrogation.used),false);
  await two.locator('#leave-solo-friend').click();
  await host.waitForFunction(()=>state.team.count===1);
  await host.locator('#nav [data-solo-tab="chat"]').click();
  assert.equal(await host.locator('#copy-solo-invite').isEnabled(),true);
  await click(extra,'#invite-entry button[type=submit]');
  await extra.waitForFunction(()=>state?.me.friend);
  assert.equal(await extra.evaluate(()=>state.day),2);
  await extra.reload();
  await extra.waitForFunction(()=>state?.me.friend && state.me.alive);
  await host.screenshot({path:'/tmp/mafia-solo-team.png'});
  await post('leave',lead); lead=null;
  for(const page of [one,extra]) await page.waitForFunction(()=>session===null);
  assert.deepEqual(errors,[]);
  console.log('Solo team browser checks passed: two-friend invites, private chat, shared investigation/question quota/ballot, next-round reset, reload, replacement friend and room closure.');
 } finally {
  if(lead) await post('leave',lead).catch(()=>{});
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
