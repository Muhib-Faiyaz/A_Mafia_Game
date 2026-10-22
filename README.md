# Mafia · After dark

A mobile-first multiplayer Mafia game. Each player joins on their own phone;
the Flask server acts as moderator. No database or account is required.

## Run

```sh
pip install -r requirements.txt
python app.py
```

For deployment, use the single-worker Gunicorn command in `Procfile` (also
configured in `railway.json`). Rooms live in memory and are cleared by a server
restart. Optional variables: `NIGHT_STEP_SECONDS` (default 30),
`DISCUSS_SECONDS` (default 120), and `PORT` (development default 5000).

## Lobby and night rules

- Choose **1, 2, or 3 Mafia**. The default, including automatic selection, is 1.
- A game needs at least 3 players and more non-Mafia players than Mafia: at
  least 3, 5, or 7 players respectively. Bots can fill empty seats.
- Enable Doctor/Detective roles or play with Mafia and Villagers only.
- Night timers cannot be skipped by the host. Each confirmed target is final
  for that turn. Mafia voting closes when all living Mafia have voted or the
  timer expires. Doctor and Detective turns advance immediately on confirmation
  or when their existing timer expires. Eliminated roles are skipped automatically.
- Unanimous votes select that person. Split votes select one random person
  uniformly from the distinct nominated targets. The target is locked once
  voting closes. On timeout, submitted votes count; no votes means no kill.
- With special roles enabled, the Doctor and Detective act before dawn. The
  Doctor can protect the locked target. The outcome appears in the town record
  when night ends. Without special roles, the kill resolves immediately.
- During discussion, every living player (including Mafia and special roles)
  can press **Proceed to vote**. The counter and town chat show readiness. Voting
  opens when all living players are ready, or after the unchanged discussion
  timeout. Each player counts once; bots mark themselves ready automatically.

The Detective receives a private right/wrong result immediately after confirming
one investigation each night. A correct result reminds the Detective not to
directly reveal who the killer is, but to convince the town through discussion
and reasoning. Results remain in the Detective's private case file; the reminder
is guidance, not an automatic chat filter.

## Online play and solo stories

The first screen offers **Online play** (the existing create/join room workflow)
and **Solo run**. Solo run chooses one of 20 original, authored mystery openings
and introduces six named characters before starting any timer. The latest case
is excluded when choosing another story in the same browser.

You play the Detective, with six NPCs including two randomized Mafia, a Doctor,
and three Villagers. Their occupations, relationships, and personal secrets do
not determine their faction. The Detective cannot be killed or voted out during
any solo round, though Mafia can still win by reaching parity with the town.
Night and discussion durations are unchanged; the cast and settings stay fixed.

Open **Detective team · Invite friends** in the briefing or during play, then
copy the invitation link. Up to **two friends** can join before or after the
first night. They help with the same Detective seat, keeping the cast at seven:

- One shared investigation per night. The first confirmed target is final,
  and every teammate receives the same private result and case notes.
- One shared readiness vote and one ballot. Any teammate can submit a choice;
  changing a ballot replaces the team's vote while voting remains open.
- A separate **Detective team chat**, available throughout the case. Bots and
  town chat never receive these messages. Only the lead speaks in town chat.
- Start, restart, and end controls remain with the lead. Friends can leave to
  free a friend seat; closing the case or choosing another story as lead closes
  the old room for everyone. Reloading resumes each participant's own session.

Treat the invitation link as private: anyone holding it can fill an open friend
seat. A room code alone cannot join a solo case. Detective points belong to the
single Detective seat; inviting friends does not multiply points.

The case dossier remains available during play. Ask a character in town chat:

- `@Mara, where were you before the first alarm?`
- `@Mara, what are you hiding?`
- `@Mara, who do you trust?`
- `@Mara, who are you?`

Use the actual name in your cast. Characters give their own accounts, protect
embarrassing personal information, and may disclose it after further questioning
or a statement of trust. Alibis refer to the first alarm, not newly invented
night events. Disclosed honesty and pre-existing relationships modestly affect
other bots' suspicions; neither proves innocence. Up to four additional direct
player-interview replies per character per day are reserved beyond the ordinary
six-message bot budget. Results, eliminations, and endings stay within the
selected case's setting. Replay keeps the cast and redeals Mafia roles; choosing
another story starts a new room and resets session scores.

These are authored openings and bounded character interactions, not full novels
or unrestricted AI improvisation. No external AI service or credentials are
needed. In-memory progress survives a page reload but not a server restart.

The MIT-licensed [novel-writing skill](.agents/skills/novel-writing/SKILL.md) was
re-downloaded and verified at its pinned revision, then applied to the original
scenario prose and character knowledge model. See [solo story design and source
notes](docs/solo-story-design.md) and `data/solo_scenarios.json`.

## Talking with bots

Bots now use a small local dialogue and voting model rather than random chat
and random daytime votes. They can accuse, defend themselves, disagree, ask for
reasons, and respond to players or other bots. No external AI service or API key
is required; this is a basic rule-based model, not unrestricted natural-language
understanding.

Use full player names in town chat, for example:

- `I suspect Alex` or `Alex is Mafia` raises suspicion of Alex.
- `I trust Alex`, `Alex is innocent`, or `don't vote Alex` argues in Alex's defense.
- `@Bot 1, why Alex?` asks that bot to explain its current preference.
- `@Bot 1, I suspect Alex` directs a claim to a specific bot.

These statements affect bot beliefs and actual votes. Before the vote closes,
new claims, defenses, or human ballots can make bots change their vote. They do
not automatically obey every message: conflicting claims, their own private
investigation, and known Mafia teammates can affect their decisions. Repeating
a claim does not keep increasing its weight. Ambiguous aliases, sarcasm, and
complex arguments may not be understood.

Bots hear public town chat only. Other players' hidden roles and private
messages are excluded, apart from the teammate information Mafia legitimately
know. Detective bots can use their own private findings
without publishing the result; Mafia bots know their teammates and try to steer
the vote away from them. Beliefs last through the current game and reset when
roles are dealt again.

At most two bot messages appear per conversation turn, with a short delay
between autonomous replies and a maximum of six messages per bot per day.
Player messages can trigger immediate responses. These limits prevent a bot
conversation from flooding the room or trapping the server in a reply loop.
They keep listening after their speaking budget is used. Bots still mark themselves ready automatically, so the human players control
how much discussion happens before voting.

## Mobile controls

The town record appears at the top. Bottom navigation jumps to the game,
players, or chat. Tap a player and confirm an action, or use the target buttons
inside Mafia chat. Town chat and private Mafia chat remain separate. Chat
supports `/vote name`; Town chat also supports `/skip` during daytime voting.

The top-right menu lets the host **end the game** (reveal roles without declaring
a winner) or **restart** (deal fresh roles while retaining players and settings).
Both actions ask for confirmation. After a game ends, the host can also return
to the lobby to change settings.

Tap the music button to enable **[It's In The Fog](https://breakingcopyright.com/song/darren-curtis-its-in-the-fog)** by **[Darren Curtis](https://www.youtube.com/user/DesperateMeasurez)**, licensed under **[Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/)**. Music powered by [BreakingCopyright](https://breakingcopyright.com).

The uploaded recording is hosted locally and converted to 128 kbps MP3 for browser playback. It attempts to start when the site opens with a two-second fade-in, plays on the landing page and in the lobby, loops continuously across turns, and shares volume and mute controls with the synthesized death and rescue effects. Playback pauses in hidden tabs and stops at game end. Browsers that block audible autoplay require a first tap, click, or keypress; explicit mute is respected. Full attribution, conversion details, and a source checksum are in [`static/audio/CREDITS.md`](static/audio/CREDITS.md) and `static/audio/sources.json`.

Every turn has its own background: crimson Mafia, teal Doctor, blue Detective,
amber discussion, and purple voting, plus distinct ending screens.

Each actual elimination creates a shared, randomly selected sad, goofy, or eerie
story. A blood-red notification names the victim and plays a synthesized impact
and splash when sound is enabled. Stories stay in the town record. Night deaths
are revealed only at dawn; a Doctor save generates no death notice. Vote-outs
get their own stories. The bank contains 18 night stories and 9 vote-out stories;
each pool is used without repeats until exhausted, then resets. Notices are remembered per player and round in browser
session storage so polling and page reloads do not repeatedly interrupt play.

The original story bank in `death_stories.py` was revised using the MIT-licensed
[`novel-writing` skill](.agents/skills/novel-writing/SKILL.md), downloaded from
[wgwtest/novel-writing](https://github.com/wgwtest/novel-writing) at revision
`838729695148008d42c01bd7c3c0c1a5c15de830`. Its unmodified package, source record,
and license are retained in `.agents/skills/novel-writing/` for future edits.
The writing follows its character-anchor, causal-scene, and concrete-ending
principles while keeping secret game roles out of the fictional anecdotes.
The skill is an authoring aid, not an external runtime dependency or AI API.

The active frontend is `static/index.html`, `static/game.css`, and
`static/game.js`. The root `index.html` mirrors the entry document as a server
fallback. No frontend build step is required.

## Session scoring

Scores appear directly beneath each player's name in the lobby and game, with
no ranking or rearrangement. They follow player identity through new role deals,
restarts, and a return to the lobby. Totals last for the in-memory room session;
a new room, room expiry, or server restart starts a new session.

- Mafia victory: **+1 to each Mafia member**, including eliminated Mafia.
- Town victory: **+1 to each surviving non-Mafia player**; the Detective’s
  total follows the rule below.
- Doctor: **+1 per actual prevented kill**, including self-protection. Protecting
  someone who was not attacked earns nothing.
- Detective: **2 total points** for correctly identifying at least one Mafia
  member and surviving a Town win, or **1 total point** for surviving a Town
  win without a correct identification. The Detective gets **0** if eliminated,
  Mafia wins, or the host ends the game. Multiple correct identifications do not
  increase the total beyond 2.

Points are held privately until the game ends, so changing totals cannot
reveal the Doctor or Detective. Settlement happens once. Earned Doctor rescue
points are kept even if the Doctor dies later. A host-ended game settles earned
Doctor action points without a victory bonus or Detective survival points.
Restarting an unfinished game discards pending points and preserves previously
settled totals.

Actual rescues create a green notification, a gentle chime (when sound is on),
and one of six shared rescue stories in the town record. The saved player is
named, but no Doctor identity or private scoring data is published. Stories are
also compatible with self-protection. A save is announced only at dawn, and does
not create a death notification.

## Tests

```sh
python -m unittest discover -s tests -v
node --check static/game.js
node tests/test_music.cjs
# With a local server running on port 5050:
node scripts/check-phase-flow.cjs
node scripts/check-bot-chat.cjs
node scripts/check-solo.cjs
node scripts/check-solo-team.cjs
```

The regression suite covers settings, role counts, split and unanimous votes,
timeouts, private chat permissions, Doctor protection, host end/restart, shared
death stories, non-repetition, notification timing, bundled audio integrity,
private scoring, one-time settlement, session retention, and anonymous rescues.

## Search visibility

The public introduction and rules are included in the server's HTML response and remain available without JavaScript. Search metadata targets online Mafia play and the Mafia board/party game without changing gameplay. Private game data stays behind the API and is excluded from indexing.

Set `SITE_URL` to your production origin (HTTPS scheme and hostname, without a path) to enable the canonical URL, absolute social sharing images, and `/sitemap.xml`. Railway's `RAILWAY_PUBLIC_DOMAIN` is used automatically when `SITE_URL` is unset. With neither configured, the game still runs, but URL-specific metadata is omitted and the sitemap returns 503 rather than advertising a development address.

See [SEO implementation and launch checks](docs/seo.md), including the installed MIT-licensed SEO and accessibility skills, validation commands, and Search Console follow-up.
