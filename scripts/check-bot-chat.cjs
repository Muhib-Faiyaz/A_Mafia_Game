// Exercise persuasion through the normal API and rendered chat, without fixtures.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, data) {
  const response = await fetch(base + '/api/' + route, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
  const result = await response.json();
  assert.equal(response.status, 200, JSON.stringify(result));
  return result;
}
(async () => {
  const host = await post('create', {name: 'Bot chat host'});
  const humans = [host];
  for (let i = 0; i < 6; i++) humans.push(await post('join', {code: host.code, name: 'Listener ' + i}));
  await post('bot', {...host, count: 3});
  let state = await post('state', host);
  const all = [...humans, ...state.players.filter(p => p.bot).map(p => ({code: host.code, pid: p.id}))];
  await post('settings', {...host, mafia_count: 2, special_roles: true});
  await post('start', host);
  const roles = {};
  for (const identity of all) roles[identity.pid] = (await post('state', identity)).me.role;
  for (let step = 0; step < 12; step++) {
    state = await post('state', host);
    if (state.phase !== 'night') break;
    const actors = humans.filter(h => roles[h.pid] === state.night_step && state.players.find(p => p.id === h.pid).alive);
    for (const identity of actors) {
      const own = await post('state', identity);
      if (own.phase !== 'night' || own.night_step !== own.me.role || own.pick) continue;
      const target = own.players.find(p => p.alive && (own.me.role === 'doctor' || p.id !== identity.pid)
        && (own.me.role !== 'mafia' || roles[p.id] !== 'mafia') && (!p.bot || own.me.role === 'detective'));
      await post('act', {...identity, target: target.id});
    }
  }
  state = await post('state', host);
  assert.equal(state.phase, 'day');
  const bot = state.players.find(p => p.bot && p.alive && roles[p.id] !== 'detective');
  const speaker = humans.find(h => state.players.find(p => p.id === h.pid).alive && h.pid !== bot.id);
  const suspect = state.players.find(p => p.alive && !p.bot && p.id !== speaker.pid && roles[p.id] !== 'mafia');
  assert.ok(bot && speaker && suspect);
  const browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  const errors = [];
  try {
    const context = await browser.newContext({viewport: {width: 390, height: 844}});
    await context.addInitScript(identity => localStorage.setItem('mafia', JSON.stringify(identity)), speaker);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.waitForFunction(() => state?.phase === 'day');
    for (const [dialog, button] of [['#investigation-dialog', '#dismiss-investigation'], ['#death-notice', '#dismiss-death']]) {
      if (await page.locator(dialog).evaluate(el => el.open)) await page.locator(button).click();
    }
    const sourceName = state.players.find(p => p.id === speaker.pid).name;
    await page.locator('#input-town').fill(`@${bot.name}, I suspect ${suspect.name}`);
    await page.locator('.composer[data-channel="town"] button').click();
    await page.waitForFunction(({botName, sourceName}) => state.chat.some(c => c.n === botName && c.t.includes('@' + sourceName)), {botName: bot.name, sourceName});
    assert.ok((await page.locator('#messages-town').innerText()).includes('@' + suspect.name));
    await page.locator('#messages-town').screenshot({path: '/tmp/mafia-bot-conversation.png'});
    for (const identity of humans) {
      const own = await post('state', identity);
      if (own.me.alive && !own.voting) await post('proceed', identity);
    }
    state = await post('state', host);
    assert.equal(state.voting, true);
    const ballot = state.players.find(p => p.id === suspect.id).votes;
    assert.ok(ballot > 0, 'The accusation changes at least one actual bot ballot');
    assert.deepEqual(errors, []);
    console.log('Bot browser check passed: player message, addressed bot response, conversation UI, and actual ballots influenced.');
  } finally {
    await browser.close();
    await post('end', host);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
