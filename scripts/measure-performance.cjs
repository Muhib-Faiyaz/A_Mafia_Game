const { chromium } = require("playwright");
const fs = require("node:fs");
(async () => {
  const label = process.argv[2] || "baseline";
  const browser = await chromium.launch({
    executablePath: "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox"],
  });
  const loads = [];
  for (let i = 0; i < 3; i++) {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    });
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
    await cdp.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 150,
      downloadThroughput: 200000,
      uploadThroughput: 93750,
    });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.addInitScript(() => {
      window.lab = { lcp: 0, cls: 0, longTasks: 0 };
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) lab.lcp = e.startTime;
      }).observe({ type: "largest-contentful-paint", buffered: true });
      new PerformanceObserver((list) => {
        for (const e of list.getEntries())
          if (!e.hadRecentInput) lab.cls += e.value;
      }).observe({ type: "layout-shift", buffered: true });
      new PerformanceObserver((list) => {
        for (const e of list.getEntries())
          lab.longTasks += Math.max(0, e.duration - 50);
      }).observe({ type: "longtask", buffered: true });
    });
    await page.goto("http://127.0.0.1:5000");
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    loads.push(
      await page.evaluate(() => ({
        ...lab,
        resources: performance
          .getEntriesByType("resource")
          .map((r) => ({
            name: r.name.split("/").pop(),
            bytes: r.encodedBodySize,
            start: r.startTime,
            end: r.responseEnd,
          })),
        fcp: performance.getEntriesByName("first-contentful-paint")[0]
          ?.startTime,
        ready: performance.now(),
      })),
    );
    await context.close();
  }
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  const post = async (route, data) =>
    (
      await fetch("http://127.0.0.1:5000/api/" + route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
    ).json();
  const host = await post("create", { name: "Perf " + label }),
    users = [host];
  for (let i = 0; i < 19; i++)
    users.push(await post("join", { code: host.code, name: "Guest " + i }));
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
  for (let i = 0; i < 30; i++) {
    await post("chat", { ...viewer, channel: "mafia", text: "Message " + i });
    await new Promise((r) => setTimeout(r, 65));
  }
  await page.evaluate(() => poll(true));
  const cdp = await context.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  const interactions = await page.evaluate(async () => {
    const result = {};
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
      let removed = 0;
      const observer = new MutationObserver((records) => {
        for (const r of records) removed += r.removedNodes.length;
      });
      observer.observe(app, { childList: true, subtree: true });
      const times = [];
      for (let i = 0; i < 10; i++) {
        const start = performance.now();
        fn();
        times.push(performance.now() - start);
        await new Promise(requestAnimationFrame);
      }
      observer.disconnect();
      result[name] = { times, removed };
    }
    return result;
  });
  const report = {
    label,
    browser: browser.version(),
    conditions: {
      viewport: "390x844",
      cpu: 4,
      network: "1.6 Mbps down, 150ms latency",
      cold: true,
    },
    loads,
    interactions,
  };
  fs.writeFileSync(
    "/tmp/mafia-perf-" + label + ".json",
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
