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

Tap the music button to enable the original procedural soundtrack: a suspense
pattern at night and softer ambient notes during the day. Music is generated
locally with Web Audio; no external music downloads or credentials are needed.
It starts only after a tap, has mute and volume controls, pauses in hidden tabs,
and stops when the game ends. Mobile devices may require unmuting their audio.

The active frontend is `static/index.html`, `static/game.css`, and
`static/game.js`. The root `index.html` mirrors the entry document as a server
fallback. No frontend build step is required.

## Tests

```sh
python -m unittest discover -s tests -v
node --check static/game.js
```

The regression suite covers settings, role counts, split and unanimous votes,
timeouts, private chat permissions, Doctor protection, and host end/restart.
