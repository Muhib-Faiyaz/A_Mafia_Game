const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5050';
async function post(route, body) {
  const response = await fetch(`${base}/api/${route}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  assert.equal(response.status, 200, data.error);
  return data;
}
(async () => {
  const browser = await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  let identity;
  try {
    const manifest = await fetch(`${base}/static/images/cases/manifest.json`).then(response => response.json());
    const page = await browser.newPage({viewport:{width:390,height:844}}), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    // Decode every shipped variant in a real browser and check its orientation.
    const assets = Object.values(manifest.stories).flatMap(story => Object.values(story.scenes).flatMap(scene =>
      ['desktop','mobile'].map(device => ({device,url:scene[device]}))));
    assert.equal(assets.length, 70);
    await page.goto(base);
    const decoded = await page.evaluate(async assets => Promise.all(assets.map(asset => new Promise(resolve => {
      const img = new Image();
      img.onload = () => resolve({...asset,width:img.naturalWidth,height:img.naturalHeight});
      img.onerror = () => resolve({...asset,error:true});
      img.src = asset.url;
    }))), assets);
    for (const asset of decoded) {
      assert.ok(!asset.error, `Cannot decode ${asset.url}`);
      assert.deepEqual([asset.width,asset.height], asset.device === 'desktop' ? [1280,720] : [540,960]);
    }
    identity = await post('solo', {name:'Art Reviewer',scenario_id:'ninth-photograph'});
    await page.evaluate(identity => localStorage.setItem('mafia',JSON.stringify(identity)), identity);
    await page.reload();
    await page.waitForFunction(() => state?.phase === 'lobby');
    await post('start', identity);
    for (const scene of ['mafia','doctor','detective','discussion','voting']) {
      await page.evaluate(() => poll(true));
      for (const width of [320,390,1440]) {
        await page.setViewportSize({width,height:900});
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const device = width <= 700 ? 'mobile' : 'desktop';
        const actual = await page.evaluate(() => getComputedStyle(document.body,'::before').backgroundImage);
        assert.ok(actual.includes(`${scene}-${device}.webp`), `${scene} at ${width}: ${actual}`);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      }
      if (scene === 'detective' || scene === 'voting') {
        for (const width of [390,1440]) {
          await page.setViewportSize({width,height:900});
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          await page.screenshot({path:`/tmp/mafia-case-art-${scene}-${width}.png`});
        }
      }
      if (scene === 'discussion') await post('proceed', identity);
      else if (scene !== 'voting') await post('solo-proceed', identity);
      if (scene === 'detective') {
        await page.evaluate(() => poll(true));
        await page.evaluate(() => {document.querySelector('#death-notice').close();document.querySelector('#investigation-dialog').close();});
      }
    }
    assert.deepEqual(errors, []);
    console.log('Case art passed: all 70 WebPs decode with correct dimensions; five live phases use mobile/desktop variants at 320/390/1440 without overflow.');
  } finally {
    await browser.close();
    if (identity) await post('leave',identity);
  }
})().catch(error => {console.error(error);process.exitCode=1;});
