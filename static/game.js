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
  detective: ["Detective", "Investigate one person each night. Keep the result private and persuade the town."],
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
  polling = null,
  updateEpoch = 0,
  busy = false;
let draft = { town: "", mafia: "", team: "" },
  recordOpen = false,
  caseOpen = false,
  journalOpen = false,
  entryMode = "",
  entryName = "",
  teamOpen = false,
  soloTab = "round",
  questionTarget = "",
  influenceTarget = "",
  storyChoice = "random",
  storyCatalog = [],
  catalogLoading = null,
  nextCaseOpen = false,
  influenceFeedback = null,
  feedbackIdentity = "",
  chatIdentity = "",
  chatTracking = null;
const invitationParams = new URLSearchParams(location.search);
let pendingInvite = invitationParams.get("case") && invitationParams.get("invite")
  ? { code: invitationParams.get("case"), invite: invitationParams.get("invite") } : null;
function clearInvitation() {
  pendingInvite = null;
  if (invitationParams.has("invite")) history.replaceState(null, "", location.pathname + location.hash);
}
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
    body: JSON.stringify({
      ...session,
      ...body,
      ...(route !== "state" ? { include_state: true } : {}),
    }),
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
  updateEpoch++;
  if (route === "solo-influence") {
    influenceFeedback = { status: "pending", message: "Submitting your stance…" };
    render();
  }
  const button = document.activeElement?.closest("button");
  button?.setAttribute("aria-busy", "true");
  try {
    const data = await api(route, body);
    if (data.state?.scenario && !data.state.tutorial) {
      try { localStorage.setItem("mafia-last-case", data.state.scenario.id); } catch (_) {}
    }
    if (data.pid) {
      if (route === "solo-join") clearInvitation();
      draft = { town: "", mafia: "", team: "" };
      selected = null;
      revealed = false;
      soloTab = "round";
      questionTarget = influenceTarget = "";
      session = { code: data.code, pid: data.pid };
      localStorage.setItem("mafia", JSON.stringify(session));
    }
    if (["start", "restart", "reset", "solo-next"].includes(route)) {
      revealed = false;
      selected = null;
      draft = { town: "", mafia: "", team: "" };
      soloTab = "round";
      questionTarget = influenceTarget = "";
      influenceFeedback = null;
      nextCaseOpen = false;
    }
    if (route === "solo-influence") {
      influenceFeedback = data.influence || { status: "accepted", message: "Stance accepted. No change to witness preferences was reported." };
      saveInfluenceFeedback();
    }
    updateEpoch++;
    if (data.feedback) toast(data.feedback);
    if (data.state) applyState(data.state);
    else if (route !== "leave") await poll(true);
    if (route === "solo-influence") render();
    return true;
  } catch (error) {
    if (route === "solo-influence") {
      influenceFeedback = { status: "rejected", message: error.message };
      saveInfluenceFeedback();
      render();
    }
    toast(error.message);
    return false;
  } finally {
    button?.removeAttribute("aria-busy");
    busy = false;
  }
}
function leaveLocal() {
  updateEpoch++;
  session = state = null;
  signature = phaseKey = "";
  entryMode = "";
  caseOpen = false;
  journalOpen = false;
  teamOpen = false;
  soloTab = "round";
  nextCaseOpen = false;
  influenceFeedback = null;
  feedbackIdentity = chatIdentity = "";
  chatTracking = null;
  questionTarget = influenceTarget = "";
  clearInvitation();
  selected = null;
  revealed = false;
  draft = { town: "", mafia: "", team: "" };
  localStorage.removeItem("mafia");
  $("#death-notice").close();
  $("#investigation-dialog").close();
  render();
}
function applyState(next) {
  deadline = next.mode !== "solo" && next.timer_left ? Date.now() + next.timer_left * 1000 : 0;
  const key = [
    next.round_id,
    next.phase,
    next.day,
    next.night_step,
    next.voting,
  ].join(":");
  if (next.round_id !== state?.round_id || next.phase === "lobby") {
    $("#death-notice").close();
    $("#investigation-dialog").close();
  }
  if (key !== phaseKey) {
    selected = null;
    if (next.round_id !== state?.round_id) revealed = false;
    phaseKey = key;
  }
  if (next.team && ((next.me.friend && !state?.team) || next.team.count > (state?.team?.count || 0))) teamOpen = true;
  if (next.mode === "solo" && next.phase === "over" && state?.phase !== "over") soloTab = "dossier";
  state = next;
  restoreInfluenceFeedback();
  if (next.scenario?.influence_feedback && !["pending", "rejected"].includes(influenceFeedback?.status)) {
    influenceFeedback = next.scenario.influence_feedback;
    saveInfluenceFeedback();
  }
  updateChatTracking();
  const sig = JSON.stringify({ ...next, timer_left: 0 });
  if (sig !== signature) {
    signature = sig;
    render();
  }
  tick();
  showInvestigation();
  showDeathNotice();
  $("#connection")?.remove();
}
function poll(force = false) {
  if (!session || (document.hidden && !force)) return Promise.resolve();
  // A requested refresh must run AFTER any older in-flight snapshot.
  if (polling) return force ? polling.then(() => poll(true)) : polling;
  const identity = session,
    epoch = updateEpoch;
  polling = (async () => {
    try {
      const next = await api("state");
      if (identity === session && epoch === updateEpoch) applyState(next);
    } catch (error) {
      if (identity !== session || epoch !== updateEpoch) return;
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
    }
  })().finally(() => {
    polling = null;
  });
  return polling;
}
function updateRoleCard() {
  const card = $("#role");
  if (!card) return;
  card.setAttribute("aria-expanded", String(revealed));
  card.querySelector(".role-icon").textContent = revealed ? "♠" : "?";
  card.querySelector("b").textContent = revealed
    ? roleName(state.me.role)
    : "Your secret identity";
  card.querySelector("small").textContent = revealed
    ? roles[state.me.role]?.[1] || ""
    : "Tap to reveal. Keep it to yourself.";
}
function selectTarget(target) {
  selected = target;
  for (const card of app.querySelectorAll("[data-player]")) {
    const picked = card.dataset.player === target;
    if (card.classList.contains("selected") !== picked) {
      card.classList.toggle("selected", picked);
      card.setAttribute("aria-pressed", String(picked));
    }
  }
  const button = $("#confirm-action"),
    label = actionLabel();
  const name =
    target === "skip"
      ? "Skip"
      : state.players.find((p) => p.id === target)?.name;
  if (button && label) {
    button.disabled = !target;
    button.textContent = label + (name ? ": " + name : "");
  }
}

function influenceStorageKey() {
  return session && state ? `mafia-influence:${session.code}:${session.pid}:${state.round_id}` : "";
}
function saveInfluenceFeedback() {
  const key = influenceStorageKey();
  if (key && influenceFeedback?.status !== "pending") {
    try { localStorage.setItem(key, JSON.stringify(influenceFeedback)); } catch (_) {}
  }
}
function restoreInfluenceFeedback() {
  const key = influenceStorageKey();
  if (key === feedbackIdentity) return;
  feedbackIdentity = key;
  influenceFeedback = null;
  try { influenceFeedback = JSON.parse(localStorage.getItem(key) || "null"); } catch (_) {}
}
function chatMessages(channel) {
  return (channel === "team" ? state?.team_chat : state?.mafia_chat) || [];
}
function isOwnMessage(message) {
  return message.speaker ? message.speaker === session?.pid : message.n === state?.me?.name;
}
function chatIsVisible(channel) {
  if (document.hidden) return false;
  const messages = $("#messages-" + channel);
  if (!messages || messages.closest("[hidden]") || messages.closest("details:not([open])")) return false;
  const rect = messages.getBoundingClientRect();
  return rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight - 72;
}
function saveChatTracking() {
  if (chatIdentity && chatTracking) {
    try { localStorage.setItem(chatIdentity, JSON.stringify(chatTracking)); } catch (_) {}
  }
}
function unreadChatCount(channel) {
  const channels = channel ? [channel] : ["team", "mafia"];
  return channels.reduce((total, ch) => total + chatMessages(ch).filter(message =>
    message.k === "msg" && !isOwnMessage(message) && message.seq > (chatTracking?.[ch]?.read || 0)).length, 0);
}
function unreadBadge(channel) {
  const count = unreadChatCount(channel);
  return count ? `<span class="unread-badge" aria-label="${count} unread teammate message${count === 1 ? "" : "s"}">${count > 99 ? "99+" : count}</span>` : "";
}
function updateChatTracking() {
  if (!session || !state) return;
  const key = `mafia-chat-read:${session.code}:${session.pid}`;
  if (key !== chatIdentity) {
    chatIdentity = key;
    chatTracking = {};
    try { chatTracking = JSON.parse(localStorage.getItem(key) || "{}"); } catch (_) {}
  }
  for (const channel of ["team", "mafia"]) {
    const messages = chatMessages(channel), max = Math.max(0, ...messages.map(message => message.seq || 0)),
      generation = channel === "team" ? "team" : state.round_id;
    if (!chatTracking[channel] || chatTracking[channel].generation !== generation) {
      // The first snapshot establishes a baseline; historical messages never replay as notifications.
      chatTracking[channel] = { generation, seen: max, read: max };
      continue;
    }
    const tracking = chatTracking[channel],
      incoming = messages.filter(message => message.seq > tracking.seen && message.k === "msg" && !isOwnMessage(message));
    tracking.seen = max;
    if (incoming.length && !chatIsVisible(channel)) {
      const last = incoming.at(-1), preview = last.t.length > 100 ? last.t.slice(0, 100) + "…" : last.t;
      toast(`${channel === "team" ? "Detective team" : "Mafia"} · ${last.n}: ${preview}`);
    }
  }
  saveChatTracking();
}
function markVisibleChatsRead() {
  if (!chatTracking) return;
  let changed = false;
  for (const channel of ["team", "mafia"]) {
    if (chatIsVisible(channel) && chatTracking[channel]?.read !== chatTracking[channel]?.seen) {
      chatTracking[channel].read = chatTracking[channel].seen;
      changed = true;
    }
  }
  if (changed) {
    saveChatTracking();
    renderNavigation();
    const badge = $("#team-panel summary .unread-badge");
    if (!unreadChatCount("team")) badge?.remove();
  }
}
function complexityMeter(complexity) {
  if (!complexity || !Number.isInteger(complexity.stars)) return "";
  const stars = Math.max(1, Math.min(5, complexity.stars));
  return `<div class="complexity-meter"><span class="complexity-stars" role="img" aria-label="Story complexity: ${stars} out of 5 stars, ${esc(complexity.label)}"><span aria-hidden="true">${"★".repeat(stars)}<span class="empty-stars">${"☆".repeat(5 - stars)}</span></span></span><span>${stars}/5 · ${esc(complexity.label)}</span>${complexity.reason ? `<p class="hint">${esc(complexity.reason)}</p>` : ""}</div>`;
}
function tutorialGuide() {
  if (!state.tutorial) return "";
  const story = state.scenario, guidance = story.tutorial_guidance || {},
    questionWitness = story.cast.find(person => person.id === guidance.question_target) || story.cast.find(person => person.name.startsWith("Mara")),
    suspect = story.cast.find(person => person.id === guidance.suspect_target) || story.cast.find(person => person.name.startsWith("Ellis")),
    questionName = questionWitness?.name || "Mara", suspectName = suspect?.name || "Ellis",
    questionUsed = story.interrogation?.used || story.revisions?.length,
    inspected = story.journal.some(entry => entry.kind === "document"), compared = story.connections.length > 0,
    influenced = ["accepted", "unchanged"].includes(influenceFeedback?.status);
  let step, text, tab = "round";
  if (state.phase === "over") {
    step = !state.ended && questionUsed && inspected && compared && influenced ? "Practice complete" : "Practice ended";
    text = "Review the Dossier for the culprit, evidence, and outcome. Practice awards no session points. Replay to try the full guided sequence, or choose a full story.";
    tab = "dossier";
  } else if (state.phase === "lobby") {
    step = "Begin a practice case";
    text = "This short case uses the same investigations, questions, evidence, influence, and votes as Solo run. Begin the first night below. There are no timers or session points.";
  } else if (state.phase === "night") {
    step = state.night_step === "mafia" ? "1 · Follow the night turns" : state.night_step === "doctor" ? "2 · The Doctor acts" : state.pick ? "4 · Read your finding" : "3 · Investigate a witness";
    text = state.night_step === "mafia" ? "You are the Detective. Proceed to let the Mafia take its turn. You cannot choose their victim." : state.night_step === "doctor" ? "Proceed to the Detective turn. The Doctor chooses whom to protect; you control your own investigation." : state.pick ? "Your confirmed investigation succeeded: its result is in Private Detective findings. Read it, close the result, and Proceed to dawn." : `Select ${suspectName} in the roster and press Investigate to confirm. Selecting alone submits nothing. Your investigation choice is final for this night. You can also try a different witness.`;
  } else if (state.voting) {
    step = "8 · Confirm a final ballot";
    text = `The dispatch evidence points toward ${suspectName}. Select that witness, then press Cast vote. Your team has one shared ballot. Suspect was persuasion; this confirmation submits your vote. Skip vote is also available.`;
  } else if (!questionUsed) {
    step = "5 · Read, then ask one question";
    text = `Dawn records the witness accounts. Read them in Case journal, then return to Round, choose ${questionName} and ask “What detail did you leave out?” Your whole team shares one question this round. An answer is recorded; a secret alone is not proof of murder.`;
  } else if (!inspected || !compared) {
    step = "6 · Inspect and compare";
    text = `Question accepted: the answer and changed statement are recorded in Case journal. ${!inspected ? "Open Case journal and Inspect the scene to collect the dispatch log. Supported comparisons are recorded as evidence arrives; Compare accounts checks whether more sources can be linked." : `Now Compare accounts. ${questionName}’s missing detail and the dispatch log support a recorded comparison. If you chose another question, the game reports when more evidence is needed; you can finish this round and try again.`} These actions do not spend another question.`;
    tab = "journal";
  } else if (!influenced) {
    step = "7 · Influence the group";
    text = `Your journal now records a supported comparison. Open Influence, choose ${suspectName}, and press Suspect. Read the response: accepted means your stance was saved; the named witnesses changed their current intentions. Zero changes is also a real result. Evidence and later actions can change the final votes.`;
    tab = "influence";
  } else {
    step = "8 · Open voting";
    text = "Your stance was accepted. Read its effect in Influence, then return to Round and Proceed to vote. Choose a witness and confirm the shared ballot. Defend reduces pressure; Withdraw removes your stance. Neither casts a ballot.";
  }
  return `<aside id="practice-guide" class="card practice-guide" aria-label="Practice tutorial"><p class="eyebrow">Practice · Real game · No points</p><h2>${step}</h2><p>${text}</p>${soloTab !== tab && state.phase !== "lobby" ? `<button data-open-tab="${tab}" class="ghost">Open ${tab === "round" ? "Round" : tab === "journal" ? "Case journal" : tab === "influence" ? "Influence" : "Dossier"}</button>` : ""}</aside>`;
}
function home() {
  return `<section id="top" class="stack opening-scene"><div class="intro opening-intro"><p class="opening-title">Mafia<span>After dark</span></p><h1>Play Mafia online.<br>Trust no one.</h1><p class="opening-description">A free online Mafia game for 3–20 players. Invite friends, uncover hidden roles, and vote to save the town. No account or download needed.</p><button id="learn-game" class="tutorial-link" aria-haspopup="dialog" aria-controls="help-dialog"><span aria-hidden="true">?</span> First night? Learn to play</button></div>
<div class="mode-choices" aria-label="Choose how to play"><button id="online-play" class="mode-choice"><strong>Online play</strong><span>Play Mafia with friends online, or use this as your conductor around the table. It handles roles, night turns, timers, and votes.</span></button><button id="solo-run" class="mode-choice solo-choice"><strong>Solo run</strong><span>Seven thriller mysteries. Six witnesses. One Mafia. Compare their stories, uncover hidden motives, and follow the evidence—alone or with up to two friends.</span></button></div>
<div class="card stack game-overview"><h2>Play the Mafia board game online</h2><p>Mafia · After dark brings the social deduction party game to your browser. Each player joins on their own phone or computer, and the game moderates the night actions, discussion, and voting.</p><h2>How to play Mafia with friends</h2><ol><li>Create a room and share its four-letter code with your friends.</li><li>Choose 1–3 Mafia and optional Doctor and Detective roles. Add bots to fill empty seats or try the game solo.</li><li>At night, Mafia choose a victim, the Doctor can protect a player, and the Detective can investigate someone.</li><li>During the day, discuss who you suspect and vote. The town wins by eliminating every Mafia member; Mafia win when they match the town in numbers.</li></ol><h2>What do you need to play?</h2><p>A modern browser and an internet connection. Rooms support 3–20 players, including bots. No account, app installation, physical board, or separate moderator is required. Each player uses their own device to keep their role secret.</p></div></section>`;
}
function invitationScreen() {
  return `<section id="top" class="card stack"><p class="eyebrow">A shared solo story</p><h1>Join the Detective team.</h1><p>Up to two friends can help the lead Detective. Share investigations, plan in private, and act through one team vote. You do not get a separate character.</p>${session ? '<p class="hint">Joining switches this tab to the invited case. Your current case stays open.</p>' : ""}<form id="invite-entry" class="stack"><label class="field">Your alias<input id="friend-name" maxlength="16" autocomplete="nickname" required></label><button class="primary" type="submit">Join this case</button></form><button id="cancel-invite" class="ghost">Back</button></section>`;
}
function detectiveTeam() {
  const team = state.team;
  if (!team) return "";
  const invite = team.invite_path ? new URL(team.invite_path, location.origin).href : "";
  return `<details id="team-panel" class="card" ${teamOpen ? "open" : ""}><summary>Detective team · ${team.count}/2 friends ${unreadBadge("team")}${invite ? " · Invite friends" : ""}</summary><div class="stack" style="margin-top:16px"><p class="hint">One Detective seat, one shared investigation, one readiness vote, and one ballot. Any teammate can confirm a choice; talk here before acting. The team shares one selected question each round and one final ballot. Plan in this private chat; the lead controls starting, replaying, and closing the case.</p><ul class="team-members">${team.members.map(member => `<li>${esc(member.name)}${member.lead ? " · Lead Detective" : " · Friend"}${member.you ? " · You" : ""}</li>`).join("")}</ul>${invite ? `<label class="field">Invite link<input id="solo-invite-link" value="${esc(invite)}" readonly aria-label="Solo invitation link"></label><button id="copy-solo-invite" ${team.count >= team.cap ? "disabled" : ""}>${team.count >= team.cap ? "Team full · two friends joined" : "Copy invite link"}</button><p class="hint">Anyone with this link can join while a friend seat is free. Maximum: two friends.</p>` : ""}${chat("team")}<button id="leave-team" class="ghost">${state.me.friend ? "Leave Detective team" : "Close this case for everyone"}</button></div></details>`;
}
async function loadStoryCatalog() {
  if (storyCatalog.length) return;
  if (catalogLoading) return catalogLoading;
  catalogLoading = (async () => {
    try {
      const response = await fetch("/api/stories", { signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw Error("The story list could not be loaded. You can still choose a random story.");
      const data = await response.json();
      storyCatalog = data.stories || [];
      if ((!session && entryMode === "solo") || nextCaseOpen) render();
    } catch (error) { toast(error.message); }
    finally { catalogLoading = null; }
  })();
  return catalogLoading;
}
function storySelector() {
  const chosen = storyCatalog.find(story => story.id === storyChoice);
  return `<div class="stack story-picker"><label class="field">Choose your story<select id="story-choice"><option value="random" ${storyChoice === "random" ? "selected" : ""}>Random story</option>${storyCatalog.map(story => `<option value="${esc(story.id)}" ${storyChoice === story.id ? "selected" : ""}>${esc(story.title)}${story.complexity ? " · " + story.complexity.stars + "/5 stars" : ""}</option>`).join("")}</select></label>${chosen ? `<article class="story-preview"><h2>${esc(chosen.title)}</h2><p>${esc(chosen.setting)}</p>${complexityMeter(chosen.complexity)}<p class="hint">${esc(chosen.pressure)}</p><p class="story-origin">Writing source: ${esc(chosen.origin?.label || "novel-writing")}</p></article>` : '<p class="hint">Let the game choose a case, or select a title. Random avoids your most recent story.</p>'}<details id="story-list"><summary>Story list and writing sources${storyCatalog.length ? " · " + storyCatalog.length + " cases" : ""}</summary>${storyCatalog.length ? `<ol class="story-catalog">${storyCatalog.map(story => `<li><b>${esc(story.title)}</b>${complexityMeter(story.complexity)}<p>${esc(story.setting)}</p><p class="hint">${esc(story.origin?.label || "novel-writing")}${story.origin?.combined_from?.length ? " · Combined from: " + story.origin.combined_from.map(esc).join(" + ") : ""}</p></li>`).join("")}</ol>` : '<p class="hint">Loading the story list…</p>'}</details></div>`;
}
function entryScreen() {
  const solo = entryMode === "solo";
  return `<section id="top" class="stack opening-scene"><div class="intro opening-intro"><p class="opening-title">Mafia<span>After dark</span></p><h1>${solo ? "Choose your mystery." : "Gather your friends."}</h1><p class="opening-description">${solo ? "Seven thriller mysteries. Six witnesses. One Mafia. Choose a story or play a random one. Follow the evidence at your own pace, alone or with up to two friends." : "Play Mafia with friends online, or use this as your conductor around the table. It handles roles, night turns, timers, and votes. Create a private room, or enter the code your host shared."}</p></div><form id="entry" class="card stack"><label class="field">Your alias<input id="name" maxlength="16" autocomplete="nickname" value="${esc(entryName)}" placeholder="What should we call you?" required></label>${solo ? storySelector() : ""}<button class="primary" type="submit">${solo ? "Enter this story" : "Create a room"}</button>${solo ? '<small>No countdowns. Read, choose one question each round, and proceed when ready.</small><button id="practice-tutorial" type="button" class="ghost">Practice tutorial</button><small>A short case with guided actions. Uses the real game; no session points.</small>' : '<label class="field">Have an invitation?<input id="code" maxlength="4" autocapitalize="characters" placeholder="4-letter room code"></label><button type="button" id="join">Join the town</button><small>3–20 players · Optional bots</small>'}</form><button id="choose-mode" class="ghost">Back to play options</button></section>`;
}
function caseContent() {
  const story = state.scenario;
  return `<div class="case-prose">${story.opening.map(p => `<p>${esc(p)}</p>`).join("")}</div><section class="stack case-cast"><h2>The people in the room</h2><p class="hint">One of these six people is the Mafia. Their accounts belong to a fixed case timeline. A private shame, a mistaken memory, or an argument is not proof of murder; compare independent details.</p>${story.cast.map(p => `<article class="case-person"><h3>${esc(p.name)} <small>${esc(p.occupation)}</small></h3><p>${esc(p.description)}</p><p class="hint">${esc(p.relationship)}</p></article>`).join("")}</section>`;
}
function soloBriefing() {
  return `<section id="top" class="stack case-scene"><div><p class="eyebrow">${state.tutorial ? "Practice tutorial" : "Solo run · One of 7 cases"}</p><h1>${esc(state.scenario.title)}</h1><p class="muted">${esc(state.scenario.setting)}</p>${complexityMeter(state.scenario.complexity)}<p class="story-origin">Writing source: ${esc(state.scenario.origin?.label || "novel-writing")}</p></div>${tutorialGuide()}${detectiveTeam()}${caseContent()}<div class="card stack"><h2>Your part in this story</h2><p>You are ${esc(state.me.name)}, the Detective. Exactly one witness is the Mafia; one other person can protect someone as the Doctor. At night, select a suspect to investigate. During the gathering, choose one witness and ask one of their three selected questions. That is your team's only question for the round. Their answer can change their statement and the case against them.</p><p>Inspect the scene and compare the accounts in Case journal. Open Influence and use Suspect or Defend, then proceed to the shared final vote when ready. Catch the Mafia to win. Replaying this case preserves its culprit and timeline.</p><p class="hint">Solo has no countdowns. Use Proceed to move through each night turn and open voting when you are ready. You are protected from vote-outs and ordinary night attacks. On a final-chance night, one more town death would let Mafia win; if you have not identified the living Mafia, you can be killed. A correct investigation or the Doctor can still protect you.</p>${soloTabHelp()}${state.me.host ? '<button id="start" class="primary">Begin the first night</button>' : '<p class="hint">The lead Detective will begin the first night.</p>'}<button id="leave" class="ghost">Back to play options</button></div></section>`;
}
function soloTabHelp() {
  return `<details class="solo-tab-help"><summary>What does each tab do?</summary><dl><dt>Round</dt><dd>Advance the round, investigate at night, read your private findings, ask your one question, and cast the team's vote.</dd><dt>Case journal</dt><dd>Read recorded accounts and statement changes. Inspect the scene, compare evidence, and review your collected exhibits.</dd><dt>Influence</dt><dd>Use Suspect, Defend, or Withdraw. Read whether the stance was accepted and whose current preference changed.</dd><dt>Dossier</dt><dd>Read the opening, cast, story source, and chapter context. After the game, read how the killing happened, who did what, and why.</dd><dt>Chat</dt><dd>Read the public witness accounts and changes. Type privately with your invited Detective teammates.</dd></dl></details>`;
}
function votingHelp() {
  return `<details id="solo-voting-help" class="card"><summary>How to influence the voting</summary><ol><li><b>Build a case.</b> Inspect the scene and compare independent accounts. A comparison gives witnesses a reason to question someone; a hidden shame alone is not proof.</li><li><b>Use your one question carefully.</b> Choose one living witness, then one of the three questions. The answer changes their statement. Your whole team shares one question for this round.</li><li><b>Suspect or Defend.</b> Select a witness in Influence. Suspect adds the team's support to the case against them; Defend reduces that pressure. One supported comparison plus your suspicion can persuade the group. An unsupported accusation alone is not enough. Withdraw removes your stance.</li><li><b>Cast the final ballot.</b> Proceed to voting, select a witness in the roster, and confirm. Suspect and Defend are persuasion, not a ballot. You and your friends still have just one shared vote.</li></ol></details>`;
}
function roundQuestions() {
  const story = state.scenario, interrogation = story.interrogation || {used:false, choices:[]},
    living = story.cast.filter(person => person.alive),
    canQuestion = state.phase === "day" && !state.voting && state.me.alive && !interrogation.used;
  if (!living.some(person => person.id === questionTarget)) questionTarget = state.tutorial ? story.tutorial_guidance?.question_target || living.find(person => person.name.startsWith("Mara"))?.id || living[0]?.id || "" : living[0]?.id || "";
  const witness = living.find(person => person.id === questionTarget), choices = witness?.question_options || interrogation.choices || [],
    status = interrogation.used ? `Question used this round${interrogation.target_name ? " · " + esc(interrogation.target_name) : ""}. The answer and statement change are in Case journal.` : "One question available for the team this round.";
  return `<section id="round-questions" class="card stack interrogation"><h2>One witness. One question.</h2><p id="question-count" role="status" aria-live="polite">${status}</p><label class="field">Choose the witness<select id="question-target" ${canQuestion ? "" : "disabled"}>${living.map(person => `<option value="${esc(person.id)}" ${person.id === questionTarget ? "selected" : ""}>${esc(person.name)}</option>`).join("")}</select></label><div class="selected-questions">${choices.map(choice => `<button data-solo-question="${esc(choice.id)}" ${canQuestion && choice.available !== false ? "" : "disabled"}${choice.reason ? ` title="${esc(choice.reason)}"` : ""}>${esc(choice.label)}</button>`).join("")}</div>${!canQuestion && !interrogation.used ? '<p class="hint">Questions open during the gathering, before voting. Choose from the offered questions; witnesses do not accept typed questions.</p>' : ""}</section>`;
}
function caseJournal() {
  const story = state.scenario, canInspect = state.phase === "day" && state.me.alive;
  return `<section id="case-journal" class="card case-scene stack"><div><h1>Case journal</h1><p class="hint">${story.journal.length} recorded entries · ${story.connections.length} comparisons. Accounts and changed statements stay here for review.</p></div><div class="story-actions"><button id="inspect-scene" class="ghost" ${canInspect ? "" : "disabled"}>Inspect the scene</button><button id="compare-accounts" class="ghost" ${canInspect ? "" : "disabled"}>Compare accounts</button></div><p class="hint">Inspecting and comparing evidence do not use your one question. Ask questions in Round; discuss a stance in Influence.</p>${story.revisions?.length ? `<section class="stack"><h2>Statements changed by your questions</h2>${story.revisions.slice().reverse().map(revision => `<article class="journal-entry"><h3>${esc(revision.name)} · Round ${revision.round}</h3><details><summary>Original statement</summary><p>${esc(revision.before)}</p></details><p><b>Revised statement:</b> ${esc(revision.after)}</p></article>`).join("")}</section>` : ""}<details id="round-accounts" open><summary>Witness accounts · Round ${state.day}</summary><div class="stack">${story.cast.filter(person=>person.statement).map(person=>`<article class="journal-entry"><h3>${esc(person.name)}${person.alive ? "" : " · Recorded account"}</h3><p>${esc(person.statement)}</p></article>`).join("") || '<p class="hint">Accounts are recorded when the gathering begins. Return to Round to advance the night.</p>'}</div></details><details id="recorded-evidence" open><summary>Recorded evidence</summary><div class="stack">${story.journal.length ? story.journal.map(entry => `<article class="journal-entry"><h3>${esc(entry.title)}</h3><p class="hint">Round ${entry.day} · ${esc(entry.kind)}${entry.archived ? " · Sealed pre-watch notes" : ""}</p><p>${esc(entry.text)}</p></article>`).join("") : '<p class="muted">Your file is empty. Accounts appear at the gathering; inspect the scene to collect exhibits.</p>'}</div></details>${story.connections.length ? `<section class="stack"><h2>Accounts compared</h2>${story.connections.map(comparison => `<article class="journal-entry"><h3>${esc(comparison.title)}</h3><p>${esc(comparison.text)}</p><p class="hint">Read together: ${comparison.sources.map(id => esc(story.journal.find(entry => entry.id === id)?.title || id)).join("; ")}.</p></article>`).join("")}</section>` : ""}</section>`;
}
function influencePanel() {
  const living = state.scenario.cast.filter(person => person.alive), pending = influenceFeedback?.status === "pending",
    enabled = state.phase === "day" && !state.voting && state.me.alive && !pending;
  if (!living.some(person => person.id === influenceTarget)) influenceTarget = state.tutorial ? state.scenario.tutorial_guidance?.suspect_target || living.find(person => person.name.startsWith("Ellis"))?.id || living[0]?.id || "" : living[0]?.id || "";
  const result = influenceFeedback, changed = result?.changed_witnesses || [];
  return `<section id="case-influence" class="card case-scene stack" aria-busy="${pending}"><h1>Influence the group</h1><p>Build a case from independent evidence, then ask the witnesses to consider your stance. Your team shares these stances.</p><label class="field">Witness to discuss<select id="influence-target" ${enabled ? "" : "disabled"}>${living.map(person => `<option value="${esc(person.id)}" ${person.id === influenceTarget ? "selected" : ""}>${esc(person.name)}</option>`).join("")}</select></label><div class="story-actions">${[["suspect","Suspect"],["defend","Defend"],["neutral","Withdraw stance"]].map(([stance,label]) => `<button data-solo-stance="${stance}" ${enabled ? "" : "disabled"}>${label}</button>`).join("")}</div><div id="influence-feedback" class="influence-feedback ${result?.status === "rejected" ? "feedback-rejected" : ""}" role="status" aria-live="polite" aria-atomic="true">${result ? `<b>${{pending:"Submitting",accepted:"Accepted",unchanged:"Already recorded",rejected:"Rejected"}[result.status] || "Result"}${result.target_name ? ": " + esc(result.target_name) : ""}</b><p>${esc(result.message)}</p>${["accepted", "unchanged"].includes(result.status) && result.changed_witnesses ? `<p>${changed.length ? `${changed.length} witness${changed.length === 1 ? " changed their" : "es changed their"} current intention${changed.length === 1 ? "" : "s"}: ${changed.map(esc).join(", ")}.` : "No witnesses changed their current intentions."}</p>` : ""}` : "Choose Suspect, Defend, or Withdraw to see whether your stance was accepted and what changed."}</div><p class="hint">Suspect adds pressure; Defend reduces it; Withdraw removes your stance. Evidence gives an accusation weight. Current intentions may change as more evidence arrives. These actions do not spend your question, guarantee a final vote, or submit your ballot.</p>${state.phase !== "day" || state.voting ? '<p class="hint">Influence is available during the gathering, before voting. Return to Round to continue.</p>' : ""}${votingHelp()}</section>`;
}
function caseDossier() {
  const story = state.scenario, chapter = story.chapters.at(-1),
    reconstruction = Array.isArray(story.reconstruction) ? story.reconstruction : story.reconstruction ? [story.reconstruction] : [];
  return `<section id="case-dossier" class="card case-scene stack"><div><h1>${esc(story.title)}</h1><p class="muted">${esc(story.setting)}</p>${complexityMeter(story.complexity)}<p class="story-origin">Writing source: ${esc(story.origin?.label || "novel-writing")}</p>${story.origin?.combined_from?.length ? `<p class="hint">Combined from: ${story.origin.combined_from.map(esc).join(" + ")}.</p>` : ""}</div>${caseContent()}${chapter ? `<section class="case-prose"><p class="eyebrow">Round ${chapter.day}</p><h2>${esc(chapter.title)}</h2><p>${esc(chapter.text)}</p></section>` : ""}${story.epilogue || reconstruction.length || story.solution ? `<section id="case-ending" class="case-prose stack"><h2>The final account</h2>${story.epilogue ? `<p>${esc(story.epilogue)}</p>` : ""}${story.consequences ? `<p>${esc(story.consequences)}</p>` : ""}${reconstruction.length ? `<div id="case-reconstruction"><h3>How the killing happened</h3>${reconstruction.map(paragraph => `<p>${esc(paragraph)}</p>`).join("")}</div>` : ""}${story.solution ? `<section id="case-solution"><h3>Who did what, and why</h3><p>${esc(story.solution)}</p>${story.timeline?.length ? `<ol>${story.timeline.map(event => `<li>${esc(event)}</li>`).join("")}</ol>` : ""}</section>` : ""}</section>` : ""}</section>`;
}
function lobby() {
  const n = state.players.length,
    count = state.settings.mafia_count || 1,
    host = state.me.host,
    needed = Math.max(3, count * 2 + 1);
  return `<section id="top" class="stack lobby-scene"><div><p class="eyebrow">The gathering</p><h1 style="margin-top:8px">Take your seat.</h1></div>
<div class="card row spread"><div><p class="eyebrow">Invite your accomplices</p><p class="room-code">${esc(state.code)}</p></div><span class="pill">Lobby</span></div>
<div class="card stack"><div class="row spread"><h2>The guest list</h2><span class="pill">${n}/20</span></div><div class="members">${state.players.map((p) => `<span class="member"><b>${esc(p.name)}</b> ${p.host ? "♛" : ""}${p.you ? " · You" : ""}${p.bot ? " · Bot" : ""}<small class="player-score">${p.score || 0} session points</small></span>`).join("")}</div>${host ? '<div class="row"><button id="add-bot" style="flex:1">+ Add bot</button><button id="fill" style="flex:1">Fill to 7</button></div>' : ""}</div>
<div class="card stack"><h2>Set the stakes</h2><label class="field">Number of Mafia<select id="count" ${host ? "" : "disabled"}>${[1, 2, 3].map((i) => `<option value="${i}" ${count === i ? "selected" : ""}>${i} Mafia${i === 1 ? " · default" : ""}</option>`).join("")}</select></label><label class="field">Special characters<select id="special" ${host ? "" : "disabled"}><option value="yes" ${state.settings.special_roles ? "selected" : ""}>Doctor & Detective</option><option value="no" ${!state.settings.special_roles ? "selected" : ""}>Mafia & Villagers only</option></select></label><p class="hint">1–3 Mafia. Start with at least ${needed} players for this setup. Special characters are added as space allows.</p></div>
${host ? `<button id="start" class="primary" ${n < needed ? "disabled" : ""}>Begin the night</button>` : '<p class="muted">The host will begin when everyone is ready.</p>'}<button id="leave" class="ghost">Leave this room</button></section>`;
}
function canAct(p) {
  if (!state.me.alive || !p.alive || p.protected) return false;
  if (state.phase === "day") return state.voting && !p.you;
  if (state.pick || state.phase !== "night" || state.night_step !== state.me.role)
    return false;
  return state.me.role === "mafia"
    ? p.role !== "mafia"
    : state.me.role === "doctor" || (state.me.role === "detective" && !p.you);
}
function actionLabel() {
  if (state.phase === "day") return state.voting ? "Cast vote" : null;
  if (!state.pick && state.phase === "night" && state.night_step === state.me.role)
    return {
      mafia: "Vote to kill",
      doctor: "Protect",
      detective: "Investigate",
    }[state.me.role];
  return null;
}
function chat(channel) {
  const mafia = channel === "mafia", team = channel === "team",
    messages = team ? state.team_chat : mafia ? state.mafia_chat : state.chat,
    open = team ? !!state.team : mafia ? state.mafia_chat_open : state.mode !== "solo" && state.chat_mode;
  const kill =
    mafia &&
    state.phase === "night" &&
    state.night_step === "mafia" &&
    state.me.alive && !state.pick;
  return `<section class="card chat-card ${mafia ? "private" : ""}"><div class="row spread"><h2>${team ? "Detective team chat" : mafia ? "Mafia chat" : "Town chat"}</h2><span class="pill">${team || mafia ? "Private" : "Public"}</span></div><div class="messages" id="messages-${channel}" role="log" aria-label="${team ? "Detective team" : mafia ? "Mafia" : "Town"} messages">${messages.length ? messages.map((c) => `<div class="message ${c.k === "sys" ? "system" : ""}">${c.n ? `<b>${esc(c.n)}</b>` : ""}${esc(c.t)}</div>`).join("") : '<p class="hint">No whispers yet.</p>'}</div>
${open ? `<form class="composer" data-channel="${channel}"><input id="input-${channel}" aria-label="${team ? "Detective team" : mafia ? "Mafia" : "Town"} message" maxlength="${team ? 500 : 200}" autocomplete="off" placeholder="${team ? "Plan with your friends…" : mafia ? "Whisper to your team…" : "Share your suspicions…"}" value="${esc(draft[channel])}"><button class="primary" aria-label="Send ${channel} message">↑</button></form><p class="hint" style="margin-top:10px">${team ? "Only the Detective team can read this. Bots do not hear these messages. This chat is open throughout the case." : mafia ? "Only Mafia can see this. Use /vote name during your turn." : state.mode === "solo" ? "Use the case journal or ask @Name about their account, what they noticed, or what they are hiding. Trust and accusations affect testimony and votes. Compare accounts and inspect the scene. Repeated questions do not repeat speeches." : "Bots listen to accusations and defenses. Try “I suspect Alex”, “I trust Alex”, or “@Bot 1, why Alex?” Use full player names. Use /vote name or /skip when voting opens."}</p>` : '<p class="hint">' + (state.mode === "solo" ? "Witness accounts are read-only. Choose one of the three questions in Round; only private team chat accepts typed messages." : state.phase === "night" ? "The town is asleep. Chat reopens at dawn." : "You can watch, but cannot send messages right now.") + "</p>"}
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
        )}</div><p class="hint">Confirming fixes your target for this turn. The last Mafia vote advances the game. Split votes randomly choose one nominated person.</p></div>`
    : ""
}
${mafia && state.mafia_picks.length ? `<p class="hint" style="margin-top:12px">${state.mafia_picks.map(esc).join("<br>")}</p>` : ""}</section>`;
}
function game() {
  if (state.mode === "solo") return soloGame();
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
  return `<div id="top" class="stack"><div class="row spread"><p class="eyebrow">${state.mode === "solo" ? "Solo run" : "Room " + esc(state.code)} · ${state.players.filter((p) => p.alive).length} alive</p><span class="pill">${over ? "Finished" : night ? "After dark" : "Town meeting"}</span></div>
${state.scenario ? caseDossier() : ""}<section class="card record"><details id="record" ${recordOpen ? "open" : ""}><summary>Town record <span aria-hidden="true">⌄</span></summary><ol>${state.log.map((l) => `<li>Day ${l.d}: ${esc(l.t)}</li>`).join("")}</ol></details><p class="latest">${esc(state.log[0]?.t || "The town waits.")}</p></section>
<section class="card phase-card ${night ? "" : "day"}"><div class="row spread"><div><p class="eyebrow">${over ? "The final chapter" : night ? roleName(state.night_step) + " turn" : state.voting ? "Voting open" : "Discussion time"}</p><h1>${title}</h1></div>${!over && state.timer_total ? '<span class="clock" id="clock" aria-label="Time remaining"></span>' : ""}</div><p class="muted">${subtitle}</p>${!over && state.timer_total ? '<div class="progress" aria-hidden="true"><span id="progress"></span></div>' : ""}
${m.at_risk ? '<p id="solo-danger" class="connection" role="status">Final-chance night: one more town death lets Mafia win. Your team has not identified a surviving Mafia member, so you can be killed tonight. Find one before dawn to keep your protection.</p>' : ""}${night && state.pick ? '<p class="hint">Your target is confirmed. Waiting for the other Mafia members.</p>' : ""}${night ? '<p class="hint" style="margin-top:12px">Confirmed targets advance the turn automatically. Otherwise, the timer runs to the end.</p>' : !over && !state.voting ? `<div class="stack" style="margin-top:12px"><p id="proceed-count" role="status" aria-live="polite">${state.discussion.ready}/${state.discussion.total} players ready to vote</p>${m.alive ? `<button id="proceed-vote" class="primary" ${state.discussion.voted ? "disabled" : ""}>${state.discussion.voted ? "Waiting for the others…" : "Proceed to vote"}</button>` : ""}<p class="hint">Voting opens when every living player is ready, or when the timer ends.</p></div>` : ""}</section>
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
<section id="players"><p class="hint score-hint">Session scores stay with each player. Points update when the game ends.</p><div class="section-title"><h2>The town</h2><span class="pill">${state.players.length} seats</span></div><div class="players">${state.players.map((p) => `<button class="player ${!p.alive ? "dead" : ""} ${pick === p.id ? "selected" : ""}" data-player="${p.id}" ${canAct(p) ? "" : "disabled"} aria-pressed="${pick === p.id}"><span class="avatar">${esc(p.name[0])}</span><b>${esc(p.name)}</b><span class="player-score">${p.score || 0} point${p.score === 1 ? "" : "s"}${over && p.round_points ? ` · +${p.round_points} this game` : ""}</span><small>${p.you ? state.team ? "Detective team · " : "You · " : ""}${p.role ? roleName(p.role) : p.alive ? "Identity unknown" : "Eliminated"}${p.bot ? state.mode === "solo" ? " · Character" : " · Bot" : ""}</small>${p.votes ? `<span class="votes">${p.votes} vote${p.votes === 1 ? "" : "s"}</span>` : ""}</button>`).join("")}</div>
${label && m.alive ? `<div class="action">${state.voting ? '<button id="skip-vote" class="ghost">Skip vote (' + state.skips + ")</button>" : ""}<button id="confirm-action" class="primary" ${pick ? "" : "disabled"}>${label}${pickName ? ": " + esc(pickName) : ""}</button><p class="hint">${state.pick ? "Your choice is recorded. You may change it while the turn stays open." : "Tap a player, then confirm your choice. Night targets are final."}</p></div>` : ""}
${state.voting && m.host ? '<button id="tally" class="ghost" style="width:100%;margin-top:12px">Close voting & count votes</button>' : ""}</section>
<div id="chats" class="stack">${detectiveTeam()}${chat("town")}${m.role === "mafia" ? chat("mafia") : ""}</div>
${state.mode === "solo" && m.friend ? '<button id="leave-solo-friend" class="ghost">Leave Detective team</button>' : ""}${over && m.host ? state.mode === "solo" ? '<button id="play-again" class="primary">Replay this case</button><button id="new-case">Choose another story</button>' : '<button id="play-again" class="primary">Restart with fresh roles</button><button id="back-lobby">Back to lobby & settings</button>' : ""}</div>`;
}
function soloGame() {
  const night = state.phase === "night", over = state.phase === "over", me = state.me,
    pick = selected || state.pick, label = actionLabel(),
    title = over ? state.ended ? "Case ended" : state.winner === "town" ? "The Mafia is caught." : "Mafia wins." :
      (night ? "Night " : "Round ") + String(state.day).padStart(2,"0"),
    selectedName = pick === "skip" ? "Skip" : state.players.find(person => person.id === pick)?.name;
  const phase = `<section class="card phase-card ${night ? "" : "day"}"><p class="eyebrow">${over ? "The final chapter" : night ? roleName(state.night_step) + " turn" : state.voting ? "Voting open" : "Gathering"}</p><h1>${title}</h1><p class="muted">${over ? "Read the Dossier for the full reconstruction and motive." : night ? state.night_step === "detective" ? "Choose a suspect to investigate, then proceed to dawn. You may also proceed without investigating." : roleName(state.night_step) + " is taking their turn. Proceed when ready to move on." : state.voting ? "Select a witness below and confirm the team's one final ballot." : "Read the accounts, choose your one question, and weigh the evidence. Proceed to voting when ready."}</p>${me.at_risk ? '<p id="solo-danger" class="connection" role="status">Final-chance night: one more town death lets Mafia win. Your team has not identified the living Mafia, so you can be killed. A correct investigation can restore your protection.</p>' : ""}${night && me.alive ? `<button id="solo-proceed" class="primary">${state.night_step === "detective" ? state.pick ? "Proceed to dawn" : "Proceed without investigating" : "Proceed to " + (state.night_step === "mafia" ? "Doctor turn" : "Detective turn")}</button>` : ""}${!night && !over && !state.voting && me.alive ? '<button id="proceed-vote" class="primary">Proceed to vote</button>' : ""}<p class="hint">No timers. The case advances when your team chooses to proceed.</p></section>`;
  const roster = `<section id="players"><div class="section-title"><h2>The witnesses</h2><span class="pill">${state.players.filter(person=>person.alive).length} alive</span></div><p class="hint">${night ? "During the Detective turn, select a living witness and confirm an investigation." : state.voting ? "Select a living witness and confirm your ballot, or choose Skip vote." : "Ask your question below. Inspect evidence in Case journal and discuss a stance in Influence. This roster becomes your ballot when voting opens."}</p><div class="players">${state.players.map(person => `<button class="player ${!person.alive ? "dead" : ""} ${pick === person.id ? "selected" : ""}" data-player="${person.id}" ${canAct(person) ? "" : "disabled"} aria-pressed="${pick===person.id}"><span class="avatar">${esc(person.name[0])}</span><b>${esc(person.name)}</b><span class="player-score">${person.score || 0} points${over && person.round_points ? " · +" + person.round_points + " this game" : ""}</span><small>${person.you ? "Detective team · " : ""}${person.role ? roleName(person.role) : person.alive ? "Identity unknown" : "Eliminated"}</small>${person.votes ? `<span class="votes">${person.votes} vote${person.votes===1 ? "" : "s"}</span>` : ""}</button>`).join("")}</div>${label && me.alive ? `<div class="action">${state.voting ? '<button id="skip-vote" class="ghost">Skip vote</button>' : ""}<button id="confirm-action" class="primary" ${pick ? "" : "disabled"}>${label}${selectedName ? ": " + esc(selectedName) : ""}</button><p class="hint">${night ? "Your investigation choice is final for this night. Proceed after reading the result." : "Your friends share this one ballot. A new choice replaces it while voting is still open."}</p></div>` : ""}</section>`;
  return `<div id="top" class="stack solo-game"><div class="row spread"><p class="eyebrow">${state.tutorial ? "Practice" : "Solo run"} · ${esc(state.scenario.title)}</p><span class="pill">${over ? "Finished" : "At your pace"}</span></div>${tutorialGuide()}${soloTabHelp()}<section id="solo-tab-round" class="stack solo-tab-panel" role="tabpanel" aria-labelledby="tab-round" ${soloTab === "round" ? "" : "hidden"}>${phase}<button id="role" class="role-button" aria-expanded="${revealed}"><span class="role-icon">${revealed ? "♠" : "?"}</span><span><b>${revealed ? roleName(me.role) : "Your secret identity"}</b><small>${revealed ? esc(roles[me.role]?.[1]) : "Tap to reveal. Keep it to yourself."}</small></span></button>${state.notes.length ? `<section class="card"><p class="eyebrow">Private Detective findings</p><p>${state.notes.map(esc).join("<br>")}</p></section>` : ""}${roster}${roundQuestions()}</section><section id="solo-tab-journal" class="stack solo-tab-panel" role="tabpanel" aria-labelledby="tab-journal" ${soloTab === "journal" ? "" : "hidden"}>${caseJournal()}</section><section id="solo-tab-influence" class="stack solo-tab-panel" role="tabpanel" aria-labelledby="tab-influence" ${soloTab === "influence" ? "" : "hidden"}>${influencePanel()}</section><section id="solo-tab-dossier" class="stack solo-tab-panel" role="tabpanel" aria-labelledby="tab-dossier" ${soloTab === "dossier" ? "" : "hidden"}>${caseDossier()}</section><section id="solo-tab-chat" class="stack solo-tab-panel" role="tabpanel" aria-labelledby="tab-chat" ${soloTab === "chat" ? "" : "hidden"}><p class="hint">Public accounts and statement changes appear here. Use Round to select questions; type only in the private Detective team chat.</p>${detectiveTeam()}${chat("town")}</section>${state.mode === "solo" && me.friend ? '<button id="leave-solo-friend" class="ghost">Leave Detective team</button>' : ""}${over && me.host ? '<button id="play-again" class="primary">Replay this case</button><button id="new-case">Choose another story</button>' : ""}${nextCasePicker()}</div>`;
}
function nextCasePicker() {
  if (!nextCaseOpen || !state.me.host) return "";
  return `<section id="next-case-picker" class="card stack"><h2>Choose the next story</h2><p>Your Detective team stays in this room. Starting the next case clears this case's evidence and findings.</p>${storySelector()}<button id="confirm-next-case" class="primary">Open this story for the team</button><button id="cancel-next-case" class="ghost">Keep this case</button></section>`;
}
function switchSoloTab(tab, focus = false) {
  soloTab = tab;
  render();
  window.scrollTo({top:0,behavior:"auto"});
  markVisibleChatsRead();
  if (focus) $(`#tab-${tab}`)?.focus({preventScroll:true});
}
function renderNavigation() {
  const nav = $("#nav"), focusedTab = nav.contains(document.activeElement) ? document.activeElement.id : "";
  nav.hidden = !state || state.phase === "lobby";
  if (state?.mode === "solo") {
    nav.setAttribute("aria-label","Solo case tabs");
    nav.setAttribute("role","tablist");
    const tabs = [["round","◷","Round"],["journal","▤","Case journal"],["dossier","◈","Dossier"],["influence","⚖","Influence"],["chat","☏","Chat"]];
    const unread = unreadChatCount();
    nav.innerHTML = tabs.map(([key,icon,label]) => `<a id="tab-${key}" href="#solo-tab-${key}" data-solo-tab="${key}" role="tab" aria-label="${label}${key === "chat" && unread ? `, ${unread} unread teammate message${unread === 1 ? "" : "s"}` : ""}" aria-controls="solo-tab-${key}" aria-selected="${soloTab === key}" tabindex="${soloTab === key ? 0 : -1}"><span class="tab-icon" aria-hidden="true">${icon}${key === "chat" ? unreadBadge() : ""}</span><span>${label}</span></a>`).join("");
    nav.querySelectorAll("[data-solo-tab]").forEach(link => {
      link.onclick = event => { event.preventDefault(); switchSoloTab(link.dataset.soloTab, true); };
      link.onkeydown = event => {
        const index = tabs.findIndex(([key]) => key === link.dataset.soloTab);
        const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
        if (next < 0) return;
        event.preventDefault();
        switchSoloTab(tabs[next][0], true);
      };
    });
  } else {
    nav.setAttribute("aria-label","Game navigation");
    nav.removeAttribute("role");
    nav.innerHTML = `<a href="#top">◈<span>Game</span></a><a href="#players">♟<span>Players</span></a><a href="#chats">☏<span>Chat ${unreadBadge()}</span></a>`;
  }
  if (focusedTab) document.getElementById(focusedTab)?.focus({preventScroll:true});
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

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let motionKey = "";
function animateMoment(element, frames, duration = 420) {
  if (
    !element ||
    reducedMotion.matches ||
    typeof element.animate !== "function"
  )
    return;
  return element.animate(frames, {
    duration,
    easing: "cubic-bezier(.2,.7,.2,1)",
  });
}
function turnMoment() {
  const key = state
    ? [session?.code, state.round_id, state.day, atmosphere()].join(":")
    : "home";
  if (key === motionKey) return;
  motionKey = key;
  const cue = $("#turn-cue");
  clearTimeout(turnMoment.timer);
  cue.classList.remove("visible");
  if (!state || state.phase === "lobby") return;
  const names = {
    mafia: "The hunt begins",
    doctor: "The Doctor is awake",
    detective: "The investigation begins",
    discussion: "The town gathers",
    voting: "Time to name the killer",
    victory: "The town survives",
    defeat: "The Mafia takes the town",
    ended: "The final chapter",
  };
  cue.textContent = names[atmosphere()] || "A new chapter";
  cue.classList.add("visible");
  animateMoment(
    cue,
    [
      { opacity: 0, transform: "translate(-50%, -12px)" },
      { opacity: 1, transform: "translate(-50%, 0)" },
    ],
    380,
  );
  animateMoment(
    $(".phase-card"),
    [
      { opacity: 0.35, transform: "perspective(800px) rotateX(-7deg)" },
      { opacity: 1, transform: "perspective(800px) rotateX(0deg)" },
    ],
    650,
  );
  turnMoment.timer = setTimeout(() => cue.classList.remove("visible"), 2200);
}
reducedMotion.addEventListener("change", () => {
  if (reducedMotion.matches)
    document.getAnimations().forEach((animation) => animation.cancel());
});

// Private results are acknowledged once per player, investigation and round.
let investigationSeen = "";
function showInvestigation() {
  const result = state?.investigation;
  if (!session || !result || state.me.role !== "detective" || document.hidden) return;
  const key = `mafia-investigation:${session.code}:${session.pid}:${state.round_id}`;
  const identity = key + result.id;
  if (investigationSeen === identity) return;
  try { if (sessionStorage.getItem(key) === result.id) return; } catch (_) {}
  const dialog = $("#investigation-dialog");
  if (dialog.open || $("#help-dialog").open || $("#death-notice").open) return;
  $("#investigation-title").textContent = result.correct ? "Your suspicion was right" : "Your suspicion was wrong";
  $("#investigation-result").textContent = result.name + (result.correct ? " is Mafia." : " is not Mafia.");
  $("#investigation-reminder").textContent = result.reminder;
  dialog.dataset.result = result.id;
  dialog.dataset.key = key;
  dialog.dataset.identity = identity;
  $("#game-menu").close();
  dialog.showModal();
}
$("#dismiss-investigation").onclick = () => $("#investigation-dialog").close();
$("#investigation-dialog").addEventListener("close", () => {
  const dialog = $("#investigation-dialog");
  investigationSeen = dialog.dataset.identity;
  try { sessionStorage.setItem(dialog.dataset.key, dialog.dataset.result); } catch (_) {}
  showDeathNotice();
});

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
  if ($("#death-notice").open || $("#help-dialog").open || $("#investigation-dialog").open) return;
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
  animateMoment(
    $("#death-notice"),
    rescued
      ? [
          { opacity: 0, transform: "scale(.96)" },
          { opacity: 1, transform: "scale(1)" },
        ]
      : [
          { opacity: 0, transform: "scale(.88) rotate(-2deg)" },
          { opacity: 1, transform: "scale(1) rotate(0deg)" },
        ],
    rescued ? 650 : 480,
  );
  if (rescued) music.rescueChime();
  else music.deathStrike();
}
$("#dismiss-death").onclick = () => $("#death-notice").close();
$("#death-notice").addEventListener("close", () => {
  showInvestigation();
  // A restart may close an old notice before the next state is assigned.
  setTimeout(showDeathNotice, 0);
});

function render() {
  const focusedElement = document.activeElement;
  const focused = focusedElement?.id,
    selection = document.activeElement?.selectionStart,
    scrolls = {};
  const members = $(".members"),
    memberScroll = members?.scrollTop;
  for (const ch of ["town", "mafia", "team"]) {
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
  const turnBackground = state?.turn_background,
    mobileBackground = state?.turn_background_mobile;
  const validTurnBackground = path => typeof path === "string" &&
    /^\/static\/images\/(?:turns\/[a-zA-Z0-9_-]+\.(?:jpg|webp)|cases\/[a-z0-9-]+\/[a-z0-9-]+-(?:desktop|mobile)\.webp)$/.test(path);
  const hasTurnBackground =
    validTurnBackground(turnBackground);
  document.body.dataset.turnBackground = String(hasTurnBackground);
  if (hasTurnBackground) {
    document.body.style.setProperty(
      "--turn-background",
      `url("${turnBackground}")`,
    );
  } else {
    document.body.style.removeProperty("--turn-background");
  }
  if (validTurnBackground(mobileBackground)) {
    document.body.style.setProperty("--turn-background-mobile", `url("${mobileBackground}")`);
  } else {
    document.body.style.removeProperty("--turn-background-mobile");
  }
  renderNavigation();
  const markup = pendingInvite && (!session || session.code !== pendingInvite.code.toUpperCase()) ? invitationScreen() : !session
    ? entryMode ? entryScreen() : home()
    : !state
      ? '<p class="muted">Entering the town…</p>'
      : state.phase === "lobby"
        ? state.mode === "solo" ? soloBriefing() : lobby()
        : game();
  const target = app.cloneNode(false);
  target.innerHTML = markup;
  morphdom(app, target, {
    childrenOnly: true,
    getNodeKey: (node) =>
      node.id ||
      (node.dataset?.player ? "player:" + node.dataset.player : undefined),
    onBeforeElUpdated: (from, to) => {
      if (from.matches?.(".case-interview, #case-solution")) to.open = from.open;
      if (from === document.activeElement && from.matches("input,textarea"))
        return false;
      return !from.isEqualNode(to);
    },
  });
  const on = (id, handler) => {
    const el = $(id);
    if (el) el.onclick = handler;
  };
  on("#learn-game", openHelp);
  if ($("#invite-entry")) $("#invite-entry").onsubmit = async event => {
    event.preventDefault();
    const old = state?.me.friend ? session : null;
    if (await run("solo-join", { ...pendingInvite, name: $("#friend-name").value })) {
      if (old) { try { await api("leave", old); } catch (_) {} }
    }
  };
  on("#cancel-invite", () => { clearInvitation(); render(); });
  for (const [id, mode] of [["#online-play", "online"], ["#solo-run", "solo"]]) {
    on(id, () => { entryMode = mode; render(); if (mode === "solo") loadStoryCatalog(); $("#name")?.focus(); });
  }
  on("#choose-mode", () => { entryMode = ""; render(); });
  on("#practice-tutorial", () => run("tutorial", {name: $("#name")?.value || "Detective"}));
  app.querySelectorAll("[data-open-tab]").forEach(button => { button.onclick = () => switchSoloTab(button.dataset.openTab); });
  if ($("#story-choice")) $("#story-choice").onchange = event => { storyChoice = event.target.value; render(); };
  if (!session && entryMode && $("#entry")) {
    $("#name").oninput = e => { entryName = e.target.value; };
    $("#entry").onsubmit = (e) => {
      e.preventDefault();
      let previous = null;
      try { previous = localStorage.getItem("mafia-last-case"); } catch (_) {}
      run(entryMode === "solo" ? "solo" : "create", { name: $("#name").value, previous_scenario: previous, scenario_id: storyChoice });
    };
    if ($("#story-choice")) $("#story-choice").onchange = event => { storyChoice = event.target.value; render(); };
    on("#join", () =>
      run("join", { name: $("#name").value, code: $("#code").value }),
    );
  }
  if (state?.phase === "lobby" && state.mode !== "solo" && !$("#invite-entry")) {
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
  if (state?.mode === "solo" && !$("#invite-entry")) {
    if ($("#team-panel")) $("#team-panel").ontoggle = () => { teamOpen = $("#team-panel").open; markVisibleChatsRead(); };
    on("#copy-solo-invite", async () => {
      const input = $("#solo-invite-link");
      try { await navigator.clipboard.writeText(input.value); toast("Invite link copied. You can invite up to two friends."); }
      catch (_) { input.focus(); input.select(); toast("Select and copy this invite link."); }
    });
    const leaveTeam = async () => { if (await run("leave")) leaveLocal(); };
    on("#leave-team", leaveTeam);
    on("#leave-solo-friend", leaveTeam);
    on("#start", () => run("start"));
    on("#leave", async () => { if (await run("leave")) leaveLocal(); });
    on("#new-case", () => {
      nextCaseOpen = true; render(); loadStoryCatalog();
      $("#next-case-picker")?.scrollIntoView({block:"start",behavior:"smooth"});
    });
    on("#confirm-next-case", () => run("solo-next", {scenario_id: storyChoice}));
    on("#cancel-next-case", () => { nextCaseOpen = false; render(); });
    on("#solo-proceed", () => run("solo-proceed"));
    on("#inspect-scene", () => run("solo-evidence", {action:"inspect"}));
    on("#compare-accounts", () => run("solo-evidence", {action:"compare"}));
    if ($("#question-target")) $("#question-target").onchange = event => { questionTarget = event.target.value; render(); };
    if ($("#influence-target")) $("#influence-target").onchange = event => { influenceTarget = event.target.value; };
    app.querySelectorAll("[data-solo-question]").forEach(button => {
      button.onclick = () => run("solo-question", {target:questionTarget,question:button.dataset.soloQuestion});
    });
    app.querySelectorAll("[data-solo-stance]").forEach(button => {
      button.onclick = () => run("solo-influence", {target:influenceTarget,stance:button.dataset.soloStance});
    });
  }
  on("#role", () => {
    revealed = !revealed;
    updateRoleCard();
    animateMoment(
      $("#role"),
      [
        { transform: "perspective(700px) rotateY(-16deg)", opacity: 0.45 },
        { transform: "perspective(700px) rotateY(0deg)", opacity: 1 },
      ],
      420,
    );
  });
  on("#proceed-vote", () => run("proceed"));
  on("#tally", () => run("tally"));
  on("#skip-vote", () => {
    selectTarget("skip");
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
        selectTarget(el.dataset.player);
        animateMoment(
          $(".player.selected"),
          [
            { transform: "scale(.96)" },
            { transform: "scale(1.025)", offset: 0.55 },
            { transform: "scale(1)" },
          ],
          320,
        );
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
      if (!(await run(ch === "team" ? "team-chat" : "chat", { channel: ch, text }))) {
        draft[ch] = text;
        const current = $("#input-" + ch);
        if (current) current.value = text;
      }
      $("#input-" + ch)?.focus({ preventScroll: true });
    };
  });
  for (const ch of ["town", "mafia", "team"]) {
    const el = $("#messages-" + ch),
      old = scrolls[ch];
    if (el) el.scrollTop = !old || old.end ? el.scrollHeight : old.top;
  }
  if (members?.isConnected) members.scrollTop = memberScroll;
  const restore = focused ? document.getElementById(focused) : null;
  if (restore && restore !== focusedElement) {
    restore.focus({ preventScroll: true });
    if (typeof selection === "number" && restore.type === "text")
      restore.setSelectionRange(selection, selection);
  }
  markVisibleChatsRead();
  tick();
  turnMoment();
  music.sync();
}
function tick() {
  const left = deadline
    ? Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
    : 0;
  const clock = $("#clock"),
    progress = $("#progress");
  const text = Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
  if (clock && clock.textContent !== text) clock.textContent = text;
  if (progress) {
    const transform = `scaleX(${Math.min(1, left / (state?.timer_total || 1))})`;
    if (progress.style.transform !== transform)
      progress.style.transform = transform;
  }
  if (deadline && left === 0) {
    deadline = 0;
    poll();
  }
}

function openMenu() {
  const active = state && ["day", "night"].includes(state.phase),
    host = state?.me.host;
  $("#menu-body").innerHTML =
    `<p class="muted">${state ? "Room " + esc(state.code) + " · " + esc(state.me.name) : "Make yourself at home in the shadows."}</p><button id="menu-music">${music.enabled ? "Mute" : "Enable"} soundtrack</button><label class="field">MUSIC VOLUME<input id="volume" class="volume" type="range" min="0" max="100" value="${Math.round(music.volume * 100)}"></label><p class="hint">“It’s In The Fog” by Darren Curtis loops throughout every turn. Sound effects share this volume and mute control. Music fades in when the site opens, or on your first interaction if the browser blocks autoplay. Music pauses when you leave this tab.</p><details class="music-credits"><summary>Session scoring</summary><p>Each Mafia member gets 1 point for a Mafia win. Surviving town members get 1 for a town win (the Detective’s total follows the rule below). Doctors earn 1 for each actual rescue. A Detective who survives a town win gets 2 total points after at least one correct Mafia identification, or 1 without one. An eliminated Detective, a Mafia win, or a host-ended game gives the Detective 0.</p><p>Points appear only after the game ends. Totals stay with the player through restarts. Restarting an unfinished game discards its unclaimed points.</p></details><details class="music-credits"><summary>Music credits</summary><p><a href="https://breakingcopyright.com/song/darren-curtis-its-in-the-fog" target="_blank" rel="noopener noreferrer">It's In The Fog</a> by <a href="https://www.youtube.com/user/DesperateMeasurez" target="_blank" rel="noopener noreferrer">Darren Curtis</a> | Creative Commons (BY 3.0) | <a href="https://creativecommons.org/licenses/by/3.0/" target="_blank" rel="noopener noreferrer">License</a></p><p>Music powered by <a href="https://breakingcopyright.com" target="_blank" rel="noopener noreferrer">BreakingCopyright</a>. Converted to MP3 for playback; loops in game.</p><a href="/static/audio/CREDITS.md" target="_blank" rel="noopener">Full credits ↗</a></details>${host && state.phase !== "lobby" ? '<button id="restart-game">Restart game</button>' : ""}${host && active ? '<button id="end-game" class="danger">End game for everyone</button>' : ""}${!host && active ? '<p class="hint">Only the host can end or restart the game.</p>' : ""}`;
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
    `<p>${action === "end" ? "End the game for everyone? Roles will be revealed, with no winner declared." : state.mode === "solo" ? "Replay this case for the team? Evidence and progress will be cleared. The culprit and case timeline stay the same." : "Restart for everyone? Current progress will be cleared and fresh roles dealt. Players and settings stay the same."}</p><button id="confirm-host" class="danger">${action === "end" ? "End game" : "Restart game"}</button><button id="cancel-host">Cancel</button>`;
  $("#confirm-host").onclick = async () => {
    if (await run(action)) $("#game-menu").close();
  };
  $("#cancel-host").onclick = openMenu;
}
// Darren Curtis, CC BY 3.0; autoplay follows browser audio permissions.
// Sources, license and checksums: /static/audio/sources.json and CREDITS.md.
const SOUNDTRACK = "/static/audio/its-in-the-fog.mp3";
const SOUNDTRACKS = Object.fromEntries(
  ["ambient", "mafia", "detective", "voting", "doctor", "discussion"].map((mode) => [mode, SOUNDTRACK]),
);
const music = {
  enabled: true,
  volume: 0.3,
  context: null,
  bus: null,
  mode: "",
  buffers: new Map(),
  activeTrack: null,
  requestedTrack: "",
  trackVersion: 0,
  voices: new Set(),
  init() {
    if (this.context) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) throw Error("Audio is unavailable in this browser.");
    this.context = new AC();
    this.bus = this.context.createGain();
    this.bus.gain.setValueAtTime(0, this.context.currentTime);
    const limiter = this.context.createDynamicsCompressor();
    limiter.threshold.value = -18;
    limiter.ratio.value = 8;
    this.bus.connect(limiter);
    limiter.connect(this.context.destination);
    this.context.addEventListener("statechange", () => this.sync());
  },
  start() {
    if (!this.enabled) return;
    try {
      this.init();
      // resume() can stay pending until a gesture; do not block initialization.
      this.context.resume().then(() => this.sync()).catch(() => {});
      this.sync();
    } catch (e) {
      this.enabled = false;
      this.updateButton();
    }
  },
  async toggle() {
    this.enabled = !this.enabled;
    if (this.enabled) this.start();
    else this.sync();
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
    if (this.buffers.has(path)) {
      const cached = this.buffers.get(path);
      this.buffers.delete(path);
      this.buffers.set(path, cached);
      return cached;
    }
    const promise = fetch(path, { signal: AbortSignal.timeout(30000) })
      .then((response) => {
        if (!response.ok) throw new Error("Music file unavailable");
        return response.arrayBuffer();
      })
      .then((bytes) => this.context.decodeAudioData(bytes));
    this.buffers.set(path, promise);
    // MP3 files expand substantially in memory. Keep only two decoded tracks;
    // the HTTP cache supplies earlier tracks without another full download.
    while (this.buffers.size > 2)
      this.buffers.delete(this.buffers.keys().next().value);
    promise.catch(() => {
      if (this.buffers.get(path) === promise) this.buffers.delete(path);
    });
    return promise;
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
      this.enabled && !document.hidden && this.context?.state === "running"
        ? SOUNDTRACKS[mode] || "" : "";
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
        gain.gain.linearRampToValueAtTime(0.9, this.context.currentTime + 2);
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
          : !state || state.phase === "lobby" ? "ambient" : "";
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
function openHelp() {
  $("#game-menu").close();
  const guide = $("#help-dialog");
  if (!guide.open) guide.showModal();
  guide.scrollTop = 0;
  animateMoment(
    guide,
    [
      { opacity: 0, transform: "translateY(16px)" },
      { opacity: 1, transform: "translateY(0)" },
    ],
    300,
  );
}
$("#help").onclick = openHelp;
$("#close-help").onclick = $("#finish-help").onclick = () =>
  $("#help-dialog").close();
$("#help-dialog").addEventListener("close", () =>
  setTimeout(() => { showInvestigation(); showDeathNotice(); }, 0),
);
$("#music").onclick = () => music.toggle();
$("#menu").onclick = openMenu;
$("#close-menu").onclick = () => $("#game-menu").close();
window.addEventListener("scroll", markVisibleChatsRead, {passive:true});
window.addEventListener("resize", markVisibleChatsRead, {passive:true});
document.addEventListener("visibilitychange", () => {
  markVisibleChatsRead();
  music.sync();
  showInvestigation();
  if (!document.hidden) poll(true);
});
// Retry blocked autoplay from a real gesture; an explicit mute stays muted.
for (const event of ["click", "touchend", "keydown"]) {
  document.addEventListener(event, () => {
    if (music.enabled && music.context?.state !== "running") music.start();
  });
}
music.start();
render();
poll();
setInterval(() => poll(), 1200);
setInterval(() => {
  if (!document.hidden) tick();
}, 250);
