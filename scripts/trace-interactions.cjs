const { chromium } = require("playwright"),
  fs = require("node:fs");
(async () => {
  const label = process.argv[2];
  const browser = await chromium.launch({
    executablePath: "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const post = async (route, data) =>
    (
      await fetch("http://127.0.0.1:5000/api/" + route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
    ).json();
  const host = await post("create", { name: "Trace " + label }),
    users = [host];
  for (let i = 0; i < 19; i++)
    users.push(await post("join", { code: host.code, name: "Trace " + i }));
  await post("start", host);
  let viewer;
  for (const u of users) {
    const s = await post("state", u);
    if (s.me.role === "mafia") viewer = u;
  }
  await page.goto("http://127.0.0.1:5000");
  await page.evaluate(
    (u) => localStorage.setItem("mafia", JSON.stringify(u)),
    viewer,
  );
  await page.reload();
  await page.waitForFunction(() => state?.phase === "night");
  await page.evaluate(() =>
    Promise.all(
      document.getAnimations().map((a) => a.finished.catch(() => {})),
    ),
  );
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await cdp.send("Tracing.start", {
    categories:
      "devtools.timeline,blink.user_timing,disabled-by-default-devtools.timeline",
    transferMode: "ReturnAsStream",
  });
  const data = await page.evaluate(async () => {
    const results = {};
    for (const [name, fn] of [
      ["role", () => document.querySelector("#role").click()],
      [
        "select",
        () =>
          [...document.querySelectorAll("[data-player]")]
            .find((e) => !e.disabled)
            .click(),
      ],
    ]) {
      const samples = [];
      for (let i = 0; i < 10; i++) {
        await new Promise(requestAnimationFrame);
        const input = document.querySelector("#input-mafia"),
          start = performance.now();
        fn();
        const processing = performance.now() - start;
        await new Promise(requestAnimationFrame);
        await new Promise(requestAnimationFrame);
        samples.push({
          processing,
          frame: performance.now() - start,
          inputRetained: document.querySelector("#input-mafia") === input,
        });
      }
      results[name] = samples;
    }
    return results;
  });
  const done = new Promise((resolve) =>
    cdp.once("Tracing.tracingComplete", resolve),
  );
  await cdp.send("Tracing.end");
  const { stream } = await done;
  const chunks = [];
  while (true) {
    const chunk = await cdp.send("IO.read", { handle: stream });
    chunks.push(
      chunk.base64Encoded
        ? Buffer.from(chunk.data, "base64")
        : Buffer.from(chunk.data),
    );
    if (chunk.eof) break;
  }
  await cdp.send("IO.close", { handle: stream });
  fs.writeFileSync(
    "/tmp/mafia-trace-" + label + ".json",
    Buffer.concat(chunks),
  );
  fs.writeFileSync(
    "/tmp/mafia-interactions-" + label + ".json",
    JSON.stringify(data, null, 2),
  );
  console.log(JSON.stringify({ label, data }));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
