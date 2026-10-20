const { chromium } = require("playwright");
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    executablePath: "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const post = async (route, data) => {
    const r = await fetch("http://127.0.0.1:5000/api/" + route, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    assert.equal(r.status, 200, await r.clone().text());
    return r.json();
  };
  await page.goto("http://127.0.0.1:5000");
  await page.locator("#name").fill("Fast host");
  let requests = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) requests.push(r.url().split("/").pop());
  });
  await page.locator("button[type=submit]").click();
  await page.waitForFunction(() => state?.phase === "lobby");
  assert.ok(
    !requests.includes("state"),
    "create must avoid a followup state request",
  );
  const host = await page.evaluate(() => session);
  const users = [host];
  for (let i = 0; i < 19; i++)
    users.push(await post("join", { code: host.code, name: "Guest " + i }));
  await page.waitForFunction(() => state.players.length === 20);
  await page.locator(".members").evaluate((e) => {
    e.scrollTop = e.scrollHeight;
  });
  const oldScroll = await page.locator(".members").evaluate((e) => e.scrollTop);
  await page.evaluate(() => poll(true));
  assert.equal(
    await page.locator(".members").evaluate((e) => e.scrollTop),
    oldScroll,
  );
  let release;
  const gate = new Promise((r) => (release = r));
  let capturedResolve;
  const captured = new Promise((r) => (capturedResolve = r));
  await page.route(
    "**/api/state",
    async (route) => {
      const response = await route.fetch();
      capturedResolve();
      await gate;
      await route.fulfill({ response });
    },
    { times: 1 },
  );
  await page.evaluate(() => {
    window.oldSnapshot = poll();
  });
  await captured;
  await page.evaluate(() => run("start"));
  await page.waitForFunction(() => state.phase === "night");
  release();
  await page.evaluate(() => oldSnapshot);
  assert.equal(
    await page.evaluate(() => state.phase),
    "night",
    "old lobby snapshot must not overwrite action state",
  );
  let mafia;
  for (const u of users) {
    const s = await post("state", u);
    if (s.me.role === "mafia") mafia = u;
  }
  await page.evaluate((u) => {
    session = u;
    localStorage.setItem("mafia", JSON.stringify(u));
    signature = "";
    updateEpoch++;
  }, mafia);
  await page.evaluate(() => poll(true));
  await page.locator("#input-mafia").fill("draft message");
  await page.locator("#input-mafia").evaluate((e) => {
    window.savedInput = e;
    e.focus();
    e.setSelectionRange(2, 7);
    window.savedRole = document.querySelector("#role");
    window.savedPlayer = document.querySelector("[data-player]");
  });
  await post("chat", {
    ...mafia,
    channel: "mafia",
    text: "Incoming message while typing",
  });
  await page.evaluate(() => poll(true));
  assert.ok(
    await page.evaluate(
      () =>
        savedInput === document.querySelector("#input-mafia") &&
        document.activeElement === savedInput,
    ),
  );
  assert.equal(
    await page.locator("#input-mafia").inputValue(),
    "draft message",
  );
  assert.deepEqual(
    await page
      .locator("#input-mafia")
      .evaluate((e) => [e.selectionStart, e.selectionEnd]),
    [2, 7],
  );
  assert.ok(
    await page.evaluate(
      () =>
        savedRole === document.querySelector("#role") &&
        savedPlayer === document.querySelector("[data-player]"),
    ),
  );
  await page.evaluate(() => {
    savedInput.dispatchEvent(
      new CompositionEvent("compositionstart", { bubbles: true, data: "ভা" }),
    );
    savedInput.value = "ভা";
    draft.mafia = "ভা";
  });
  await page.evaluate(() => {
    state.chat.push({ k: "sys", n: "", t: "Background update" });
    render();
  });
  assert.ok(
    await page.evaluate(
      () => savedInput === document.querySelector("#input-mafia"),
    ),
  );
  assert.equal(await page.locator("#input-mafia").inputValue(), "ভা");
  await page.evaluate(() =>
    savedInput.dispatchEvent(
      new CompositionEvent("compositionend", { bubbles: true, data: "ভা" }),
    ),
  );
  await page.locator("#role").click();
  assert.ok(
    await page.evaluate(
      () => savedInput === document.querySelector("#input-mafia"),
    ),
  );
  const target = page.locator("[data-player]:not(:disabled)").first();
  await target.click();
  assert.ok(
    await page.evaluate(
      () => savedInput === document.querySelector("#input-mafia"),
    ),
  );
  assert.equal(await target.getAttribute("aria-pressed"), "true");
  await page.locator("#skip-vote").count();
  await page.evaluate(() => {
    document.querySelector("#input-mafia").value = "Keep the player controls";
    draft.mafia = "Keep the player controls";
    state.chat.push({ k: "sys", n: "", t: "Second update" });
    render();
  });
  await page.locator("#input-mafia").fill("Hello team");
  await page.waitForTimeout(850);
  requests = [];
  await page.locator("[data-channel=mafia] button").click();
  await page.waitForFunction(() =>
    state.mafia_chat.some((m) => m.t === "Hello team"),
  );
  assert.equal(await page.locator("#input-mafia").inputValue(), "");
  assert.equal(requests.filter((r) => r === "chat").length, 1);
  assert.ok(
    await page.evaluate(
      () => savedInput === document.querySelector("#input-mafia"),
    ),
  );
  await page.locator("#help").click();
  await page.locator("#help-dialog[open]").waitFor();
  await page.locator("#close-help").click();
  for (const width of [320, 390, 430]) {
    await page.setViewportSize({ width, height: 844 });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
  }
  await page.evaluate(async () => {
    const originalHidden = Object.getOwnPropertyDescriptor(document, "hidden");
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: true,
    });
    const original = window.fetch;
    let stateCalls = 0;
    window.fetch = (...args) => {
      if (String(args[0]).includes("/api/state")) stateCalls++;
      return original(...args);
    };
    await poll();
    if (stateCalls !== 0) throw new Error("Hidden tabs must not poll");
    window.fetch = original;
    if (originalHidden)
      Object.defineProperty(document, "hidden", originalHidden);
    else delete document.hidden;
  });
  assert.deepEqual(errors, []);
  console.log(
    "PASS: one-response create, scroll preservation, stale-poll protection, keyed player/input retention, caret range, composition text, local role/selection updates, chat send, tutorial and mobile layout",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
