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
- The host cannot skip the Mafia turn. It closes when all living Mafia have
  voted or the timer expires. Votes can be changed until that point.
- Unanimous votes select that person. Split votes select one random person
  uniformly from the distinct nominated targets. The target is locked once
  voting closes. On timeout, submitted votes count; no votes means no kill.
- With special roles enabled, the Doctor and Detective act before dawn. The
  Doctor can protect the locked target. The outcome appears in the town record
  when night ends. Without special roles, the kill resolves immediately.

## Mobile controls

The town record appears at the top. Bottom navigation jumps to the game,
players, or chat. Tap a player and confirm an action, or use the target buttons
inside Mafia chat. Town chat and private Mafia chat remain separate. Chat
supports `/vote name`; Town chat also supports `/skip` during daytime voting.

The top-right menu lets the host **end the game** (reveal roles without declaring
a winner) or **restart** (deal fresh roles while retaining players and settings).
Both actions ask for confirmation. After a game ends, the host can also return
to the lobby to change settings.

Tap the music button to enable downloaded **CC0 recordings by AERIS MUSIC**:

- **Signal Lost:** tense cinematic music for the Mafia turn.
- **Beneath:** brooding suspense for Detective turns and daytime voting.
- **Quiet Room:** calm ambient music for Doctor turns and discussion.

Tracks are hosted locally, loop, and crossfade when the mood changes. They are
loaded only after sound is enabled, cached for the session, and compressed to
128 kbps MP3 (about 3.5 MB total). No external streaming service or credentials
are required. Music and death effects share mute and volume controls; playback
stops in hidden tabs and at game end. Mobile browsers require an initial tap.
The death impact/splash is still synthesized locally with Web Audio.

Music credits are available in the game menu and
[`static/audio/CREDITS.md`](static/audio/CREDITS.md). The publisher's CC0 license,
pinned source revision, original hashes, and delivered-file hashes are retained
beside the recordings.

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

## Tests

```sh
python -m unittest discover -s tests -v
node --check static/game.js
```

The regression suite covers settings, role counts, split and unanimous votes,
timeouts, private chat permissions, Doctor protection, host end/restart, shared
death stories, non-repetition, notification timing, and bundled audio integrity.
