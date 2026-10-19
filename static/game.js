"use strict";
const $ = (s) => document.querySelector(s),
  app = $("#app");
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const roles = {
  mafia: ["Mafia", "Work with your team. Choose one victim each night."],
  town: ["Villager", "Find the Mafia. Keep your town alive."],
  doctor: ["Doctor", "Protect one person each night, including yourself."],
  detective: ["Detective", "Investigate one person each night."],
};
const roleName = (r) => roles[r]?.[0] || "Unknown";
let session = null;
try {
  session = JSON.parse(localStorage.getItem("mafia") || "null");
} catch (_) {
  localStorage.removeItem("mafia");
}
let state = null,
  signature = "",
  phaseKey = "",
  selected = null,
  revealed = false,
  deadline = 0,
  polling = false,
  busy = false;
let draft = { town: "", mafia: "" },
  recordOpen = false;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("#toast").classList.remove("visible"), 4000);
}
async function api(route, body = {}) {
  const response = await fetch("/api/" + route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...session, ...body }),
    signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "Request failed");
    error.status = response.status;
    throw error;
  }
  return data;
}
async function run(route, body = {}) {
  if (busy) return false;
  busy = true;
  try {
    const data = await api(route, body);
    if (data.pid) {
      session = { code: data.code, pid: data.pid };
      localStorage.setItem("mafia", JSON.stringify(session));
    }
    if (["start", "restart", "reset"].includes(route)) {
      revealed = false;
      selected = null;
      draft = { town: "", mafia: "" };
    }
    await poll(true);
    return true;
  } catch (error) {
    toast(error.message);
    return false;
  } finally {
    busy = false;
  }
}
function leaveLocal() {
  session = state = null;
  signature = phaseKey = "";
  selected = null;
  revealed = false;
  draft = { town: "", mafia: "" };
  localStorage.removeItem("mafia");
  $("#death-notice").close();
  render();
}
async function poll(force = false) {
  if (!session || polling) return;
  polling = true;
  try {
    const next = await api("state");
    deadline = next.timer_left ? Date.now() + next.timer_left * 1000 : 0;
    const key = [next.round_id, next.phase, next.day, next.night_step].join(
      ":",
    );
    if (next.round_id !== state?.round_id || next.phase === "lobby")
      $("#death-notice").close();
    if (key !== phaseKey) {
      selected = null;
      if (next.round_id !== state?.round_id) revealed = false;
      phaseKey = key;
    }
    state = next;
    const sig = JSON.stringify({ ...next, timer_left: 0 });
    if (sig !== signature || force) {
      signature = sig;
      render();
    }
    tick();
    showDeathNotice();
    $("#connection")?.remove();
  } catch (error) {
    if (error.status === 404) {
      leaveLocal();
      toast("This room has closed. Create or join another room.");
    } else if (!$("#connection")) {
      const note = document.createElement("p");
      note.id = "connection";
      note.className = "connection";
      note.textContent = "Connection interrupted. Reconnecting…";
      app.prepend(note);
    }
  } finally {
    polling = false;
  }
}
function home() {
  return `<section id="top" class="stack"><div class="intro"><p class="eyebrow">A game of secrets & suspicion</p><h1>The town sleeps.<br><em>Trust no one.</em></h1><p class="muted">One phone. One secret identity. Gather your friends and survive the night.</p></div>
<div class="cover" aria-hidden="true"><svg class="silhouette" viewBox="0 0 120 140"><path d="M13 140q3-42 47-45 44 3 47 45" fill="#09080d"/><path d="m48 98 12 30 12-30" fill="#b7a89c"/><path d="m57 110 6 0 3 30H54" fill="#9b293e"/><ellipse cx="60" cy="75" rx="22" ry="27" fill="#09080d"/><path d="M30 57q3-40 30-40t30 40" fill="#09080d"/><path d="M30 47h60v9H30" fill="#9b293e"/><ellipse cx="60" cy="60" rx="43" ry="8" fill="#09080d"/></svg><span class="cover-caption">EVERYONE HAS SOMETHING TO HIDE.</span></div>
<form id="entry" class="card stack"><label class="field">YOUR ALIAS<input id="name" maxlength="16" autocomplete="nickname" placeholder="What should we call you?" required></label><button class="primary" type="submit">Create a room →</button><label class="field">HAVE AN INVITATION?<input id="code" maxlength="4" autocapitalize="characters" placeholder="4-letter room code"></label><button type="button" id="join">Join the town</button><small>3–20 players · Add bots to try it solo</small></form></section>`;
}
function lobby() {
  const n = state.players.length,
    count = state.settings.mafia_count || 1,
    host = state.me.host,
    needed = Math.max(3, count * 2 + 1);
  return `<section id="top" class="stack"><div><p class="eyebrow">The gathering</p><h1 style="margin-top:8px">Take your seat.</h1></div>
<div class="card row spread"><div><p class="eyebrow">Invite your accomplices</p><p class="room-code">${esc(state.code)}</p></div><span class="pill">Lobby</span></div>
<div class="card stack"><div class="row spread"><h2>The guest list</h2><span class="pill">${n}/20</span></div><div class="members">${state.players.map((p) => `<span class="member"><b>${esc(p.name)}</b> ${p.host ? "♛" : ""}${p.you ? " · You" : ""}${p.bot ? " · Bot" : ""}<small class="player-score">${p.score || 0} session points</small></span>`).join("")}</div>${host ? '<div class="row"><button id="add-bot" style="flex:1">+ Add bot</button><button id="fill" style="flex:1">Fill to 7</button></div>' : ""}</div>
<div class="card stack"><h2>Set the stakes</h2><label class="field">NUMBER OF MAFIA<select id="count" ${host ? "" : "disabled"}>${[1, 2, 3].map((i) => `<option value="${i}" ${count === i ? "selected" : ""}>${i} Mafia${i === 1 ? " · default" : ""}</option>`).join("")}</select></label><label class="field">SPECIAL CHARACTERS<select id="special" ${host ? "" : "disabled"}><option value="yes" ${state.settings.special_roles ? "selected" : ""}>Doctor & Detective</option><option value="no" ${!state.settings.special_roles ? "selected" : ""}>Mafia & Villagers only</option></select></label><p class="hint">1–3 Mafia. Start with at least ${needed} players for this setup. Special characters are added as space allows.</p></div>
${host ? `<button id="start" class="primary" ${n < needed ? "disabled" : ""}>Begin the night →</button>` : '<p class="muted">The host will begin when everyone is ready.</p>'}<button id="leave" class="ghost">Leave this room</button></section>`;
}
function canAct(p) {
  if (!state.me.alive || !p.alive) return false;
  if (state.phase === "day") return state.voting && !p.you;
  if (state.phase !== "night" || state.night_step !== state.me.role)
    return false;
  return state.me.role === "mafia"
    ? p.role !== "mafia"
    : state.me.role === "doctor" || (state.me.role === "detective" && !p.you);
}
function actionLabel() {
  if (state.phase === "day") return state.voting ? "Cast vote" : null;
  if (state.phase === "night" && state.night_step === state.me.role)
    return {
      mafia: "Vote to kill",
      doctor: "Protect",
      detective: "Investigate",
    }[state.me.role];
  return null;
}
function chat(channel) {
  const mafia = channel === "mafia",
    messages = mafia ? state.mafia_chat : state.chat,
    open = mafia ? state.mafia_chat_open : state.chat_mode;
  const kill =
    mafia &&
    state.phase === "night" &&
    state.night_step === "mafia" &&
    state.me.alive;
  return `<section class="card chat-card ${mafia ? "private" : ""}"><div class="row spread"><h2>${mafia ? "Mafia chat" : "Town chat"}</h2><span class="pill">${mafia ? "Private" : "Public"}</span></div><div class="messages" id="messages-${channel}" role="log" aria-label="${mafia ? "Mafia" : "Town"} messages">${messages.length ? messages.map((c) => `<div class="message ${c.k === "sys" ? "system" : ""}">${c.n ? `<b>${esc(c.n)}</b>` : ""}${esc(c.t)}</div>`).join("") : '<p class="hint">No whispers yet.</p>'}</div>
${open ? `<form class="composer" data-channel="${channel}"><input id="input-${channel}" aria-label="${mafia ? "Mafia" : "Town"} message" maxlength="200" autocomplete="off" placeholder="${mafia ? "Whisper to your team…" : "Share your suspicions…"}" value="${esc(draft[channel])}"><button class="primary" aria-label="Send ${channel} message">↑</button></form><p class="hint" style="margin-top:10px">${mafia ? "Only Mafia can see this. Use /vote name during your turn." : "Use /vote name or /skip when voting opens."}</p>` : '<p class="hint">' + (state.phase === "night" ? "The town is asleep. Chat reopens at dawn." : "You can watch, but cannot send messages right now.") + "</p>"}
${
  kill
    ? `<div class="stack" style="margin-top:18px"><p class="eyebrow">Choose the victim</p><div class="targets">${state.players
        .filter((p) => p.alive && p.role !== "mafia")
        .map(
          (p) =>
            `<button data-kill="${p.id}" class="${state.pick === p.id ? "primary" : ""}">${state.pick === p.id ? "✓ " : ""}${esc(p.name)}</button>`,
        )
        .join(
          "",
        )}</div><p class="hint">The last Mafia vote locks the target. Split votes randomly choose one of the nominated people.</p></div>`
    : ""
}
${mafia && state.mafia_picks.length ? `<p class="hint" style="margin-top:12px">${state.mafia_picks.map(esc).join("<br>")}</p>` : ""}</section>`;
}
function game() {
  const night = state.phase === "night",
    over = state.phase === "over",
    m = state.me,
    label = actionLabel(),
    pick = selected || state.pick;
  const title = over
    ? state.ended
      ? "Game ended"
      : state.winner === "mafia"
        ? "Mafia wins."
        : "Town survives."
    : (night ? "Night " : "Day ") + String(state.day).padStart(2, "0");
  const subtitle = over
    ? "All identities are revealed."
    : night
      ? state.night_step === "mafia"
        ? "The Mafia are choosing their victim."
        : "Mafia voting is closed. " +
          roleName(state.night_step) +
          " is awake. The outcome arrives at dawn."
      : state.voting
        ? "The verdict is yours. Vote to eliminate."
        : "Talk quietly. Listen closely. Find the liar.";
  const pickName =
    pick === "skip" ? "Skip" : state.players.find((p) => p.id === pick)?.name;
  return `<div id="top" class="stack"><div class="row spread"><p class="eyebrow">Room ${esc(state.code)} · ${state.players.filter((p) => p.alive).length} alive</p><span class="pill">${over ? "Finished" : night ? "After dark" : "Town meeting"}</span></div>
<section class="card record"><details id="record" ${recordOpen ? "open" : ""}><summary>Town record <span aria-hidden="true">⌄</span></summary><ol>${state.log.map((l) => `<li>Day ${l.d}: ${esc(l.t)}</li>`).join("")}</ol></details><p class="latest">${esc(state.log[0]?.t || "The town waits.")}</p></section>
<section class="card phase-card ${night ? "" : "day"}"><div class="row spread"><div><p class="eyebrow">${over ? "The final chapter" : night ? roleName(state.night_step) + " turn" : state.voting ? "Voting open" : "Discussion time"}</p><h1>${title}</h1></div>${!over && state.timer_total ? '<span class="clock" id="clock" aria-label="Time remaining"></span>' : ""}</div><p class="muted">${subtitle}</p>${!over && state.timer_total ? '<div class="progress" aria-hidden="true"><span id="progress"></span></div>' : ""}
${state.can_skip && (night || !state.voting) ? `<button class="ghost" id="skip-timer" style="margin-top:12px">${night ? "Skip this role" : "Open voting"}</button>` : ""}${night && state.night_step === "mafia" ? '<p class="hint" style="margin-top:12px">This timer cannot be skipped by the host.</p>' : ""}</section>
<button id="role" class="role-button" aria-expanded="${revealed}"><span class="role-icon">${revealed ? "♠" : "?"}</span><span><b>${revealed ? roleName(m.role) : "Your secret identity"}</b><small>${revealed ? esc(roles[m.role]?.[1]) : "Tap to reveal. Keep it to yourself."}</small></span></button>
${!m.alive ? '<p class="connection">You have been eliminated. Watch the town from the shadows.</p>' : ""}
${
  m.role === "mafia" && !over
    ? `<p class="hint">Your team: ${
        state.players
          .filter((p) => p.role === "mafia" && !p.you)
          .map((p) => esc(p.name))
          .join(", ") || "You work alone."
      }</p>`
    : ""
}
${state.notes.length ? `<div class="card"><p class="eyebrow">Detective’s case file</p><p>${state.notes.map(esc).join("<br>")}</p></div>` : ""}
<section id="players"><p class="hint score-hint">Session scores stay with each player. Points update when the game ends.</p><div class="section-title"><h2>The town</h2><span class="pill">${state.players.length} seats</span></div><div class="players">${state.players.map((p) => `<button class="player ${!p.alive ? "dead" : ""} ${pick === p.id ? "selected" : ""}" data-player="${p.id}" ${canAct(p) ? "" : "disabled"} aria-pressed="${pick === p.id}"><span class="avatar">${esc(p.name[0])}</span><b>${esc(p.name)}</b><span class="player-score">${p.score || 0} point${p.score === 1 ? "" : "s"}${over && p.round_points ? ` · +${p.round_points} this game` : ""}</span><small>${p.you ? "You · " : ""}${p.role ? roleName(p.role) : p.alive ? "Identity unknown" : "Eliminated"}${p.bot ? " · Bot" : ""}</small>${p.votes ? `<span class="votes">${p.votes} vote${p.votes === 1 ? "" : "s"}</span>` : ""}</button>`).join("")}</div>
${label && m.alive ? `<div class="action">${state.voting ? '<button id="skip-vote" class="ghost">Skip vote (' + state.skips + ")</button>" : ""}<button id="confirm-action" class="primary" ${pick ? "" : "disabled"}>${label}${pickName ? ": " + esc(pickName) : ""}</button><p class="hint">${state.pick ? "Your choice is recorded. You may change it while the turn stays open." : "Tap a player, then confirm your choice."}</p></div>` : ""}
${state.voting && m.host ? '<button id="tally" class="ghost" style="width:100%;margin-top:12px">Close voting & count votes</button>' : ""}</section>
<div id="chats" class="stack">${chat("town")}${m.role === "mafia" ? chat("mafia") : ""}</div>
${over && m.host ? '<button id="play-again" class="primary">Restart with fresh roles</button><button id="back-lobby">Back to lobby & settings</button>' : ""}</div>`;
}
function atmosphere() {
  if (!state) return "home";
  if (state.phase === "night") return state.night_step;
  if (state.phase === "day") return state.voting ? "voting" : "discussion";
  if (state.phase === "over")
    return state.ended
      ? "ended"
      : state.winner === "mafia"
        ? "defeat"
        : "victory";
  return "lobby";
}

// Remember notices per player and round so polling/reloads never replay a death.
let deathIdentity = "",
  deathSeen = new Set();
function showDeathNotice() {
  if (
    !session ||
    !state?.round_id ||
    document.hidden ||
    state.phase === "lobby"
  )
    return;
  const storageKey = `mafia-deaths:${session.code}:${session.pid}`;
  const identity = storageKey + state.round_id;
  if (deathIdentity !== identity) {
    deathIdentity = identity;
    deathSeen = new Set();
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (saved?.round === state.round_id) deathSeen = new Set(saved.seen);
    } catch (_) {
      /* In-memory deduplication still works without storage. */
    }
  }
  if ($("#death-notice").open) return;
  const event = (state.notices || state.death_events || []).find(
    (event) => !deathSeen.has(event.id),
  );
  if (!event) return;
  deathSeen.add(event.id);
  try {
    sessionStorage.setItem(
      storageKey,
      JSON.stringify({ round: state.round_id, seen: [...deathSeen] }),
    );
  } catch (_) {}
  const rescued = event.kind === "rescue";
  $("#death-notice").classList.toggle("rescue-notice", rescued);
  $("#notice-eyebrow").textContent = rescued
    ? "A life brought back from the brink"
    : "A seat at the table falls silent";
  $("#notice-symbol").textContent = rescued ? "+" : "†";
  $("#death-title").textContent =
    event.name +
    (rescued
      ? " has been saved"
      : event.cause === "night"
        ? " has been killed"
        : " has been voted out");
  $("#death-tone").textContent = rescued
    ? "The Doctor remains anonymous"
    : {
        sad: "A tragic farewell",
        goofy: "A ridiculous end",
        eerie: "A chilling tale",
      }[event.tone] || "Town tale";
  $("#death-story").textContent = event.story;
  $("#game-menu").close();
  $("#death-notice").showModal();
  if (rescued) music.rescueChime();
  else music.deathStrike();
}
$("#dismiss-death").onclick = () => $("#death-notice").close();
$("#death-notice").addEventListener("close", () => {
  // A restart may close an old notice before the next state is assigned.
  setTimeout(showDeathNotice, 0);
});

function render() {
  const focused = document.activeElement?.id,
    selection = document.activeElement?.selectionStart,
    scrolls = {};
  for (const ch of ["town", "mafia"]) {
    const el = $("#messages-" + ch);
    if (el)
      scrolls[ch] = {
        top: el.scrollTop,
        end: el.scrollTop + el.clientHeight >= el.scrollHeight - 24,
      };
  }
  document.body.dataset.phase = state?.phase || "home";
  document.body.dataset.atmosphere = atmosphere();
  const deathBackground =
    state?.me?.alive === false && state.phase !== "lobby"
      ? state.me.death_background
      : null;
  const hasDeathBackground =
    typeof deathBackground === "string" &&
    /^\/static\/images\/dead\/[a-zA-Z0-9_.-]+$/.test(deathBackground);
  document.body.dataset.eliminated = String(hasDeathBackground);
  if (hasDeathBackground) {
    document.body.style.setProperty(
      "--death-background",
      `url("${deathBackground}")`,
    );
  } else {
    document.body.style.removeProperty("--death-background");
  }
  const turnBackground = state?.turn_background;
  const hasTurnBackground =
    typeof turnBackground === "string" &&
    /^\/static\/images\/turns\/(village|doctor|detective|discussion|voting)\.jpg$/.test(
      turnBackground,
    );
  document.body.dataset.turnBackground = String(hasTurnBackground);
  if (hasTurnBackground) {
    document.body.style.setProperty(
      "--turn-background",
      `url("${turnBackground}")`,
    );
  } else {
    document.body.style.removeProperty("--turn-background");
  }
  $("#nav").hidden = !state || state.phase === "lobby";
  app.innerHTML = !session
    ? home()
    : !state
      ? '<p class="muted">Entering the town…</p>'
      : state.phase === "lobby"
        ? lobby()
        : game();
  const on = (id, handler) => {
    const el = $(id);
    if (el) el.onclick = handler;
  };
  if (!session) {
    $("#entry").onsubmit = (e) => {
      e.preventDefault();
      run("create", { name: $("#name").value });
    };
    on("#join", () =>
      run("join", { name: $("#name").value, code: $("#code").value }),
    );
  }
  if (state?.phase === "lobby") {
    const save = () =>
      run("settings", {
        mafia_count: Number($("#count").value),
        special_roles: $("#special").value === "yes",
      });
    if (state.me.host) {
      $("#count").onchange = save;
      $("#special").onchange = save;
    }
    on("#start", () => run("start"));
    on("#add-bot", () => run("bot", { count: 1 }));
    on("#fill", () =>
      run("bot", { count: Math.max(0, 7 - state.players.length) }),
    );
    if ($("#fill")) $("#fill").disabled = state.players.length >= 7;
    if ($("#add-bot")) $("#add-bot").disabled = state.players.length >= 20;
    on("#leave", async () => {
      if (await run("leave")) leaveLocal();
    });
  }
  on("#role", () => {
    revealed = !revealed;
    render();
  });
  on("#skip-timer", () => run("skip"));
  on("#tally", () => run("tally"));
  on("#skip-vote", () => {
    selected = "skip";
    render();
  });
  on("#confirm-action", () =>
    run(state.phase === "night" ? "act" : "vote", {
      target: selected || state.pick,
    }),
  );
  on("#play-again", () => confirmHostAction("restart"));
  on("#back-lobby", () => run("reset"));
  app.querySelectorAll("[data-player]").forEach(
    (el) =>
      (el.onclick = () => {
        selected = el.dataset.player;
        render();
      }),
  );
  app
    .querySelectorAll("[data-kill]")
    .forEach(
      (el) => (el.onclick = () => run("act", { target: el.dataset.kill })),
    );
  if ($("#record"))
    $("#record").ontoggle = () => {
      recordOpen = $("#record").open;
    };
  app.querySelectorAll(".composer").forEach((form) => {
    const ch = form.dataset.channel,
      input = $("#input-" + ch);
    input.oninput = () => {
      draft[ch] = input.value;
    };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      draft[ch] = "";
      input.value = "";
      if (!(await run("chat", { channel: ch, text }))) {
        draft[ch] = text;
        const current = $("#input-" + ch);
        if (current) current.value = text;
      }
      $("#input-" + ch)?.focus({ preventScroll: true });
    };
  });
  for (const ch of ["town", "mafia"]) {
    const el = $("#messages-" + ch),
      old = scrolls[ch];
    if (el) el.scrollTop = !old || old.end ? el.scrollHeight : old.top;
  }
  const restore = focused ? document.getElementById(focused) : null;
  if (restore) {
    restore.focus({ preventScroll: true });
    if (typeof selection === "number" && restore.type === "text")
      restore.setSelectionRange(selection, selection);
  }
  tick();
  music.sync();
}
function tick() {
  const left = deadline
    ? Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
    : 0;
  if ($("#clock"))
    $("#clock").textContent =
      Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
  if ($("#progress"))
    $("#progress").style.width =
      Math.min(100, (left / (state?.timer_total || 1)) * 100) + "%";
  if (deadline && left === 0) {
    deadline = 0;
    poll();
  }
}
function openMenu() {
  const active = state && ["day", "night"].includes(state.phase),
    host = state?.me.host;
  $("#menu-body").innerHTML =
    `<p class="muted">${state ? "Room " + esc(state.code) + " · " + esc(state.me.name) : "Make yourself at home in the shadows."}</p><button id="menu-music">${music.enabled ? "Mute" : "Enable"} soundtrack</button><label class="field">MUSIC VOLUME<input id="volume" class="volume" type="range" min="0" max="100" value="${Math.round(music.volume * 100)}"></label><p class="hint">A different track for every turn: cinematic Mafia tension, brooding Detective music, dark voting music, calm Doctor ambience and warm discussion music. Sound effects share this volume and mute control. Music pauses when you leave this tab.</p><details class="music-credits"><summary>Session scoring</summary><p>Each Mafia member gets 1 point for a Mafia win. Surviving town members get 1 for a town win. Doctors earn 1 for each actual rescue, and Detectives earn 1 for each different Mafia member correctly identified.</p><p>Points appear only after the game ends. Totals stay with the player through restarts. Restarting an unfinished game discards its unclaimed points.</p></details><details class="music-credits"><summary>Music credits</summary><p>“Signal Lost”, “Beneath”, “Ash”, “Quiet Room” and “Afterglow Vast” by AERIS MUSIC. Released under CC0 1.0; compressed for mobile playback.</p><a href="https://github.com/farmmer938-lgtm/aeris-cc0-music" target="_blank" rel="noopener noreferrer">Artist’s collection ↗</a> · <a href="/static/audio/CREDITS.md" target="_blank" rel="noopener">License details ↗</a></details>${host && state.phase !== "lobby" ? '<button id="restart-game">Restart game</button>' : ""}${host && active ? '<button id="end-game" class="danger">End game for everyone</button>' : ""}${!host && active ? '<p class="hint">Only the host can end or restart the game.</p>' : ""}`;
  $("#menu-music").onclick = async () => {
    await music.toggle();
    $("#menu-music").textContent =
      (music.enabled ? "Mute" : "Enable") + " soundtrack";
  };
  $("#volume").oninput = (e) => music.setVolume(Number(e.target.value) / 100);
  if ($("#restart-game"))
    $("#restart-game").onclick = () => confirmHostAction("restart");
  if ($("#end-game")) $("#end-game").onclick = () => confirmHostAction("end");
  if (!$("#game-menu").open) $("#game-menu").showModal();
}
function confirmHostAction(action) {
  if (!$("#game-menu").open) $("#game-menu").showModal();
  $("#menu-body").innerHTML =
    `<p>${action === "end" ? "End the game for everyone? Roles will be revealed, with no winner declared." : "Restart for everyone? Current progress will be cleared and fresh roles dealt. Players and settings stay the same."}</p><button id="confirm-host" class="danger">${action === "end" ? "End game" : "Restart game"}</button><button id="cancel-host">Cancel</button>`;
  $("#confirm-host").onclick = async () => {
    if (await run(action)) $("#game-menu").close();
  };
  $("#cancel-host").onclick = openMenu;
}
// Downloaded CC0 recordings, decoded only after a deliberate user tap.
// Sources, license and checksums: /static/audio/sources.json and CREDITS.md.
const SOUNDTRACKS = {
  mafia: "/static/audio/signal-lost.mp3",
  detective: "/static/audio/beneath.mp3",
  voting: "/static/audio/ash.mp3",
  doctor: "/static/audio/quiet-room.mp3",
  discussion: "/static/audio/afterglow-vast.mp3",
};
const music = {
  enabled: false,
  volume: 0.3,
  context: null,
  bus: null,
  mode: "",
  buffers: new Map(),
  activeTrack: null,
  requestedTrack: "",
  trackVersion: 0,
  voices: new Set(),
  async toggle() {
    try {
      if (!this.context) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) throw Error("Audio is unavailable in this browser.");
        this.context = new AC();
        this.bus = this.context.createGain();
        const limiter = this.context.createDynamicsCompressor();
        limiter.threshold.value = -18;
        limiter.ratio.value = 8;
        this.bus.connect(limiter);
        limiter.connect(this.context.destination);
      }
      this.enabled = !this.enabled;
      if (this.enabled) await this.context.resume();
      this.sync();
    } catch (e) {
      this.enabled = false;
      toast("Could not start music. Tap the music button to try again.");
    }
    this.updateButton();
  },
  updateButton() {
    const b = $("#music");
    b.setAttribute("aria-pressed", String(this.enabled));
    b.setAttribute("aria-label", this.enabled ? "Mute music" : "Enable music");
    b.textContent = this.enabled ? "♫" : "♪";
  },
  setVolume(value) {
    this.volume = value;
    this.sync();
  },
  note(freq, time, length, level, type = "sine") {
    const c = this.context,
      o = c.createOscillator(),
      g = c.createGain();
    o.type = type;
    o.frequency.value = freq;
    g.gain.setValueAtTime(0, time);
    g.gain.linearRampToValueAtTime(level, time + 0.08);
    g.gain.exponentialRampToValueAtTime(0.0001, time + length);
    o.connect(g);
    g.connect(this.bus);
    o.start(time);
    o.stop(time + length + 0.1);
    o.onended = () => {
      o.disconnect();
      g.disconnect();
    };
  },
  async loadTrack(path) {
    if (!this.buffers.has(path)) {
      const promise = fetch(path, { signal: AbortSignal.timeout(30000) })
        .then((response) => {
          if (!response.ok) throw new Error("Music file unavailable");
          return response.arrayBuffer();
        })
        .then((bytes) => this.context.decodeAudioData(bytes));
      this.buffers.set(path, promise);
      promise.catch(() => this.buffers.delete(path));
    }
    return this.buffers.get(path);
  },
  fadeOut(voice, seconds = 0.7) {
    if (!voice) return;
    const now = this.context.currentTime;
    const stopAt = now + seconds + 0.05;
    // Muting/hiding must shorten a crossfade that is already in progress.
    if (voice.stopAt && voice.stopAt <= stopAt) return;
    voice.stopping = true;
    voice.stopAt = stopAt;
    voice.gain.gain.cancelAndHoldAtTime(now);
    voice.gain.gain.linearRampToValueAtTime(0, now + seconds);
    voice.source.stop(stopAt);
  },
  syncTrack(mode) {
    const path =
      this.enabled && !document.hidden ? SOUNDTRACKS[mode] || "" : "";
    if (path === this.requestedTrack) return;
    this.requestedTrack = path;
    const version = ++this.trackVersion;
    if (!path) {
      for (const voice of this.voices) this.fadeOut(voice, 0.15);
      this.activeTrack = null;
      return;
    }
    this.loadTrack(path)
      .then((buffer) => {
        // Never start a stale download after a phase change, mute or tab hide.
        if (version !== this.trackVersion || !this.enabled || document.hidden)
          return;
        const source = this.context.createBufferSource(),
          gain = this.context.createGain();
        source.buffer = buffer;
        source.loop = true;
        gain.gain.setValueAtTime(0, this.context.currentTime);
        gain.gain.linearRampToValueAtTime(0.9, this.context.currentTime + 0.7);
        source.connect(gain);
        gain.connect(this.bus);
        const voice = { path, source, gain, stopping: false };
        this.voices.add(voice);
        source.onended = () => {
          source.disconnect();
          gain.disconnect();
          this.voices.delete(voice);
        };
        for (const previous of this.voices)
          if (previous !== voice) this.fadeOut(previous);
        this.activeTrack = voice;
        source.start();
      })
      .catch(() => {
        if (version !== this.trackVersion) return;
        for (const voice of this.voices) this.fadeOut(voice, 0.15);
        this.activeTrack = null;
        toast("Music could not load. Tap sound off and on to retry.");
      });
  },
  rescueChime() {
    if (
      !this.enabled ||
      !this.context ||
      this.context.state !== "running" ||
      document.hidden
    )
      return;
    const t = this.context.currentTime + 0.02;
    [261.63, 329.63, 392, 523.25].forEach((frequency, i) =>
      this.note(frequency, t + i * 0.16, 1.4, 0.1),
    );
  },
  deathStrike() {
    if (
      !this.enabled ||
      !this.context ||
      this.context.state !== "running" ||
      document.hidden
    )
      return;
    const c = this.context,
      t = c.currentTime + 0.02;
    // A descending impact with a short filtered splash, synthesized locally.
    const hit = c.createOscillator(),
      gain = c.createGain();
    hit.frequency.setValueAtTime(150, t);
    hit.frequency.exponentialRampToValueAtTime(32, t + 0.7);
    gain.gain.setValueAtTime(0.35, t);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 1);
    hit.connect(gain);
    gain.connect(this.bus);
    hit.start(t);
    hit.stop(t + 1.1);
    hit.onended = () => {
      hit.disconnect();
      gain.disconnect();
    };
    const buffer = c.createBuffer(
      1,
      Math.ceil(c.sampleRate * 0.55),
      c.sampleRate,
    );
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;
    const noise = c.createBufferSource(),
      filter = c.createBiquadFilter(),
      splash = c.createGain();
    noise.buffer = buffer;
    filter.type = "bandpass";
    filter.Q.value = 1.4;
    filter.frequency.setValueAtTime(1400, t);
    filter.frequency.exponentialRampToValueAtTime(220, t + 0.5);
    splash.gain.setValueAtTime(0.13, t);
    splash.gain.exponentialRampToValueAtTime(0.0001, t + 0.55);
    noise.connect(filter);
    filter.connect(splash);
    splash.connect(this.bus);
    noise.start(t);
    noise.onended = () => {
      noise.disconnect();
      filter.disconnect();
      splash.disconnect();
    };
    this.note(73.42, t + 0.15, 1.8, 0.12, "triangle");
  },
  sync() {
    const mode =
      state?.phase === "night"
        ? state.night_step
        : state?.phase === "day"
          ? state.voting
            ? "voting"
            : "discussion"
          : "";
    if (this.bus)
      this.bus.gain.setTargetAtTime(
        this.enabled && !document.hidden ? this.volume : 0,
        this.context.currentTime,
        0.15,
      );
    this.mode = mode;
    this.syncTrack(mode);
    this.updateButton();
  },
};
$("#music").onclick = () => music.toggle();
$("#menu").onclick = openMenu;
$("#close-menu").onclick = () => $("#game-menu").close();
document.addEventListener("visibilitychange", () => {
  music.sync();
  if (!document.hidden) poll(true);
});
render();
poll();
setInterval(() => poll(), 1200);
setInterval(tick, 250);
