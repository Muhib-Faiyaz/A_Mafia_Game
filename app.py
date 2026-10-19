"""Mafia — a Flask app where the server acts as the neutral Moderator.
State lives in memory, so run a single worker (see Procfile)."""
import math, os, random, string, threading, time, uuid
from flask import Flask, jsonify, request, send_from_directory
from death_stories import DEATH_STORIES

app = Flask(__name__, static_folder="static")
rooms, lock = {}, threading.RLock()
MIN_PLAYERS, MAX_PLAYERS = 3, 20
STEP = int(os.environ.get("NIGHT_STEP_SECONDS", 30))  # mafia, then doctor, then detective
STEPS = ("mafia", "doctor", "detective")
DISCUSS = int(os.environ.get("DISCUSS_SECONDS", 120))  # 2 minutes of talking before votes open


class Bad(Exception):
    def __init__(self, msg, code=400):
        self.msg, self.code = msg, code


@app.errorhandler(Bad)
def _bad(e):
    return jsonify(error=e.msg), e.code


def ctx(d):
    room = rooms.get(str(d.get("code", "")).strip().upper())
    pid = d.get("pid")
    if not room or pid not in room["players"]:
        raise Bad("Room not found. It may have expired.", 404)
    room["t"] = time.time()
    return room, pid


def clean(n):
    return " ".join(str(n or "").split())[:16]


def chat_add(room, ch, name, text, kind="msg"):
    room["chat"].append(dict(ch=ch, n=name, t=text, k=kind))
    del room["chat"][:-150]


def say(room, text):
    room["log"].append({"d": room["day"], "t": text})
    chat_add(room, "town", "", text, "sys")


def add_player(room, name, host=False, bot=False):
    if any(p["name"].lower() == name.lower() for p in room["players"].values()):
        raise Bad("That name is taken in this room.")
    pid = uuid.uuid4().hex
    room["players"][pid] = dict(name=name, role=None, alive=True, host=host, notes=[], bot=bot)
    return pid


def alive(room, role=None):
    return [i for i, p in room["players"].items()
            if p["alive"] and (role is None or p["role"] == role)]


def discussing(room):
    return room["phase"] == "day" and time.time() < room.get("discuss_until", 0)


def start_night(room):
    room["day"] += 1
    room["phase"] = "night"
    room["night"] = dict(mafia={}, doctor=None, detective=None, victim=None)
    room["votes"] = {}
    room["night_step"], room["step_until"] = STEPS[0], time.time() + STEP


def advance(room):
    """Finish Mafia voting on all ballots or timeout; keep other role timers."""
    while room["phase"] == "night":
        complete = (room["night_step"] == "mafia" and
                    all(i in room["night"]["mafia"] for i in alive(room, "mafia")))
        if not complete and time.time() < room["step_until"]:
            break
        if room["night_step"] == "mafia":
            nominees = sorted(set(room["night"]["mafia"].values()))
            room["night"]["victim"] = random.choice(nominees) if nominees else None
            if nominees:
                chat_add(room, "mafia", "", "Voting closed. A target is locked in; the outcome is revealed at dawn.", "sys")
        steps = tuple(role for role in STEPS if role == "mafia" or
                      (room["settings"]["special_roles"] and any(p["role"] == role for p in room["players"].values())))
        i = steps.index(room["night_step"])
        if i + 1 < len(steps):
            room["night_step"], room["step_until"] = steps[i + 1], time.time() + STEP
        else:
            resolve_night(room)


def timers(room):
    now = time.time()
    if room["phase"] == "night":
        return math.ceil(max(0, room["step_until"] - now)), STEP
    if room["phase"] == "day":
        return math.ceil(max(0, room.get("discuss_until", 0) - now)), DISCUSS
    return 0, 0


def check_win(room):
    m = len(alive(room, "mafia"))
    t = len(alive(room)) - m
    w = "town" if m == 0 else "mafia" if m >= t else None
    if w:
        room["phase"], room["winner"] = "over", w
        say(room, "The town wins — every Mafia member is gone." if w == "town"
            else "The Mafia wins — they now match the town in numbers.")
    return bool(w)


def night_done(room):
    n = room["night"]
    return (all(i in n["mafia"] for i in alive(room, "mafia"))
            and (n["doctor"] or not alive(room, "doctor"))
            and (n["detective"] or not alive(room, "detective")))


def record_death(room, pid, cause):
    """Publish one shared story only when an elimination actually happens."""
    player = room["players"][pid]
    if not player["alive"]:
        return
    player["alive"] = False
    stories = DEATH_STORIES[cause]
    used = room.setdefault("story_used", {}).setdefault(cause, [])
    available = [i for i in range(len(stories)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(stories)))
    index = available[random.randrange(len(available))]
    used.append(index)
    tone, template = stories[index]
    story = template.format(name=player["name"])
    event = dict(id=uuid.uuid4().hex, day=room["day"], name=player["name"],
                 player_id=pid, cause=cause, tone=tone, story=story)
    room.setdefault("death_events", []).append(event)
    say(room, story)


def resolve_night(room):
    n, P = room["night"], room["players"]
    for i in alive(room, "detective"):
        t = P.get(n["detective"])
        if t:
            P[i]["notes"].append(f"Night {room['day']}: {t['name']} is {'Mafia' if t['role'] == 'mafia' else 'not Mafia'}.")
    victim = n["victim"]
    if victim and victim != n["doctor"]:
        record_death(room, victim, "night")
        room["dawn"] = f"{P[victim]['name']} was killed."
    else:
        room["dawn"] = "Nobody was killed last night."  # nobody learns if the doctor saved someone
    say(room, f"Night {room['day']}: {room['dawn']}")
    if not check_win(room):
        room["phase"] = "day"
        room["discuss_until"] = time.time() + DISCUSS


def tally(room):
    P, counts = room["players"], {}
    for t in room["votes"].values():
        counts[t] = counts.get(t, 0) + 1
    top = max(counts.values(), default=0)
    leaders = [t for t, c in counts.items() if c == top]
    if top == 0 or len(leaders) > 1 or leaders[0] == "skip":
        say(room, f"Day {room['day']}: no majority, nobody was voted out.")
    else:
        p = P[leaders[0]]
        record_death(room, leaders[0], "vote")
        say(room, f"Day {room['day']}: {p['name']} was voted out.")
    if not check_win(room):
        start_night(room)


def label(r):
    return {"mafia": "Mafia", "town": "a Villager", "doctor": "the Doctor",
            "detective": "the Detective"}[r].replace("Mafia", "Mafia")


def cast_vote(room, pid, t):
    P = room["players"]
    if room["phase"] != "day" or not P[pid]["alive"]:
        raise Bad("You can't vote right now.")
    if discussing(room):
        raise Bad("Voting opens when the discussion timer ends.")
    if t != "skip" and (t not in P or not P[t]["alive"] or t == pid):
        raise Bad("Pick another living player, or skip.")
    prev = room["votes"].get(pid)
    room["votes"][pid] = t
    who = "skip the vote" if t == "skip" else P[t]["name"]
    chat_add(room, "town", "", f"{P[pid]['name']} {'changed their vote to' if prev else 'voted for'} {who}.", "sys")
    if all(i in room["votes"] for i in alive(room)):
        tally(room)


def find_player(room, arg):
    arg = arg.strip().lstrip("@").lower()
    live = [(i, p["name"]) for i, p in room["players"].items() if p["alive"]]
    exact = [i for i, n in live if n.lower() == arg]
    part = [i for i, n in live if arg and n.lower().startswith(arg)]
    pick = exact or (part if len(part) == 1 else [])
    if not pick:
        raise Bad(f"No living player matches '{arg}'.")
    return pick[0]


BOT_LINES = ["I think {n} is acting suspicious.", "{n} has been too quiet for me.",
             "My gut says {n} is Mafia.", "Does anyone else trust {n}? I don't.", "Watch {n} closely."]


def run_bots(room):
    """Test bots act automatically so one person can try the game alone."""
    P = room["players"]
    for _ in range(300):
        moved = False
        advance(room)
        if room["phase"] == "night":
            n, step = room["night"], room["night_step"]
            for i in alive(room):
                p, r = P[i], P[i]["role"]
                if not p["bot"] or r != step:
                    continue
                if r == "mafia" and i not in n["mafia"]:
                    mafia_vote(room, i, random.choice([x for x in alive(room) if P[x]["role"] != "mafia"]))
                    moved = True
                elif r in ("doctor", "detective") and not n[r]:
                    n[r] = random.choice([x for x in alive(room) if x != i or r == "doctor"])
                    moved = True
        elif room["phase"] == "day":
            for i in alive(room):
                if P[i]["bot"] and (room["day"], i) not in room["said"]:
                    room["said"].add((room["day"], i))
                    pool = [x for x in alive(room) if x != i and not (P[i]["role"] == "mafia" and P[x]["role"] == "mafia")]
                    if pool and random.random() < 0.7:
                        chat_add(room, "town", P[i]["name"], random.choice(BOT_LINES).format(n="@" + P[random.choice(pool)]["name"]))
            if not discussing(room):
                for i in alive(room):
                    if room["phase"] != "day":
                        break
                    if P[i]["bot"] and i not in room["votes"]:
                        opts = [x for x in alive(room) if x != i and not (P[i]["role"] == "mafia" and P[x]["role"] == "mafia")]
                        cast_vote(room, i, random.choice(opts + ["skip"]))
                        moved = True
                if room["phase"] == "day" and all(i in room["votes"] for i in alive(room)):
                    tally(room)
                    moved = True
        if not moved:
            break


def view(room, pid):
    P, me, over = room["players"], room["players"][pid], room["phase"] == "over"
    vc = {}
    if room["phase"] == "day":
        for t in room["votes"].values():
            vc[t] = vc.get(t, 0) + 1
    n = room.get("night") or {}
    pick = done = None
    if room["phase"] == "night" and me["alive"] and room["night_step"] == me["role"]:
        pick = n["mafia"].get(pid) if me["role"] == "mafia" else n.get(me["role"])
    elif room["phase"] == "day":
        pick = room["votes"].get(pid)
    mp = []
    if me["role"] == "mafia" and room["phase"] == "night":
        mp = [f"{P[a]['name']} → {P[b]['name']}" for a, b in n["mafia"].items() if a != pid]
    players = []
    for i, p in P.items():
        known = over or i == pid or (me["role"] == "mafia" and p["role"] == "mafia")
        players.append(dict(id=i, name=p["name"], bot=p["bot"], alive=p["alive"], host=p["host"], you=i == pid,
                            role=p["role"] if known else None, votes=vc.get(i, 0)))
    mode = None
    if room["phase"] == "day":
        mode = "town" if me["alive"] else None
    elif room["phase"] == "over":
        mode = "town"
    chat = [dict(c) for c in room["chat"] if c["ch"] == "town"][-80:]
    mafia_chat = [dict(c) for c in room["chat"] if c["ch"] == "mafia"][-80:] if me["role"] == "mafia" else []
    return dict(code=room["code"], chat=chat, chat_mode=mode, phase=room["phase"], day=room["day"], winner=room.get("winner"),
                death_events=room.get("death_events", []), round_id=room.get("round_id"), settings=room["settings"], ended=room.get("ended", False), mafia_chat=mafia_chat,
                mafia_chat_open=me["role"] == "mafia" and me["alive"] and room["phase"] in ("day", "night"),
                can_skip=me["host"] and (room["phase"] == "day" or (room["phase"] == "night" and room["night_step"] != "mafia")),
                min=MIN_PLAYERS, me=dict(name=me["name"], role=me["role"], alive=me["alive"], host=me["host"]),
                players=players, pick=pick, notes=me["notes"], mafia_picks=mp,
                skips=vc.get("skip", 0),
                timer_left=timers(room)[0], timer_total=timers(room)[1],
                night_step=room["night_step"] if room["phase"] == "night" else None,
                dawn=room.get("dawn") if room["phase"] == "day" else None, voting=room["phase"] == "day" and not discussing(room),
                votes_left=len(alive(room)) - len(room["votes"]) if room["phase"] == "day" else 0, log=room["log"][::-1][:40])


@app.post("/api/create")
def create():
    d = request.get_json(force=True)
    name = clean(d.get("name"))
    if not name:
        raise Bad("Enter your name first.")
    with lock:
        for c in [c for c, r in rooms.items() if time.time() - r["t"] > 6 * 3600]:
            del rooms[c]
        code = "".join(random.choices("ABCDEFGHJKMNPQRSTUVWXYZ", k=4))
        while code in rooms:
            code = "".join(random.choices("ABCDEFGHJKMNPQRSTUVWXYZ", k=4))
        rooms[code] = dict(code=code, players={}, phase="lobby", day=0, log=[], votes={}, chat=[], said=set(), t=time.time(),
                           settings=dict(special_roles=True, mafia_count=1))
        pid = add_player(rooms[code], name, host=True)
    return jsonify(code=code, pid=pid)


@app.post("/api/join")
def join():
    d = request.get_json(force=True)
    name, room = clean(d.get("name")), rooms.get(str(d.get("code", "")).strip().upper())
    if not name:
        raise Bad("Enter your name first.")
    if not room:
        raise Bad("No room with that code.", 404)
    with lock:
        if room["phase"] != "lobby":
            raise Bad("That game has already started.")
        if len(room["players"]) >= MAX_PLAYERS:
            raise Bad("That room is full.")
        pid = add_player(room, name)
    return jsonify(code=room["code"], pid=pid)


@app.post("/api/state")
def state():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        run_bots(room)
        return jsonify(view(room, pid))


@app.post("/api/bot")
def bot():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d)
        if not room["players"][pid]["host"] or room["phase"] != "lobby":
            raise Bad("Only the host can add bots in the lobby.")
        for _ in range(max(0, min(int(d.get("count") or 1), 15))):
            if len(room["players"]) >= MAX_PLAYERS:
                break
            k = 1
            while any(p["name"] == f"Bot {k}" for p in room["players"].values()):
                k += 1
            add_player(room, f"Bot {k}", bot=True)
        return jsonify(ok=True)


@app.post("/api/leave")
def leave():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        if room["phase"] == "lobby":
            was = room["players"].pop(pid)
            if not room["players"]:
                del rooms[room["code"]]
            elif was["host"]:
                next(iter(room["players"].values()))["host"] = True
        return jsonify(ok=True)


@app.post("/api/settings")
def settings():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d)
        if not room["players"][pid]["host"] or room["phase"] != "lobby":
            raise Bad("Only the host can change lobby settings.")
        special = d.get("special_roles", room["settings"]["special_roles"])
        count = d.get("mafia_count", room["settings"]["mafia_count"])
        if type(special) is not bool:
            raise Bad("Special roles must be on or off.")
        if count is None:
            count = 1
        if type(count) is not int or not 1 <= count <= 3:
            raise Bad("Choose between 1 and 3 Mafia.")
        room["settings"] = dict(special_roles=special, mafia_count=count)
        return jsonify(ok=True)


@app.post("/api/start")
def start():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        P = room["players"]
        if not P[pid]["host"] or room["phase"] != "lobby":
            raise Bad("Only the host can start the game.")
        start_game(room)
        return jsonify(ok=True)


def start_game(room):
    P = room["players"]
    n = len(P)
    if n < MIN_PLAYERS:
        raise Bad(f"You need at least {MIN_PLAYERS} players.")
    m = room["settings"]["mafia_count"] or 1
    if m * 2 >= n:
        raise Bad("Mafia must be fewer than half the players. Update the lobby settings.")
    sp = [r for k, r in enumerate(("doctor", "detective")) if room["settings"]["special_roles"] and n - m - k > 1]
    roles = ["mafia"] * m + sp + ["town"] * (n - m - len(sp))
    random.shuffle(roles)
    for p, r in zip(P.values(), roles):
        p.update(role=r, alive=True, notes=[], last=0)
    room.update(day=0, log=[], winner=None, chat=[], said=set(), ended=False, round_id=uuid.uuid4().hex, death_events=[], story_used={})
    say(room, "The game begins. Night falls on the town.")
    start_night(room)
    run_bots(room)


@app.post("/api/restart")
def restart():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        if not room["players"][pid]["host"] or room["phase"] == "lobby":
            raise Bad("Only the host can restart a game.")
        start_game(room)
        return jsonify(ok=True)


@app.post("/api/end")
def end():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        if not room["players"][pid]["host"] or room["phase"] not in ("night", "day"):
            raise Bad("Only the host can end an active game.")
        room.update(phase="over", winner=None, ended=True)
        say(room, "The host ended the game. All roles are revealed.")
        return jsonify(ok=True)


def mafia_vote(room, pid, target):
    p = room["players"][pid]
    if room["phase"] != "night" or room["night_step"] != "mafia" or not p["alive"] or p["role"] != "mafia":
        raise Bad("Mafia kill voting is only open during the Mafia turn.")
    if target not in room["players"] or not room["players"][target]["alive"] or room["players"][target]["role"] == "mafia":
        raise Bad("Choose a living player outside the Mafia.")
    room["night"]["mafia"][pid] = target
    chat_add(room, "mafia", "", f"{p['name']} voted to kill {room['players'][target]['name']}.", "sys")


@app.post("/api/act")
def act():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d)
        P, p, t = room["players"], room["players"][pid], d.get("target")
        advance(room)
        if room["phase"] != "night" or not p["alive"] or p["role"] not in ("mafia", "doctor", "detective"):
            raise Bad("You can't act right now.")
        if room["night_step"] != p["role"]:
            raise Bad("Wait until your role wakes up.")
        if t not in P or not P[t]["alive"]:
            raise Bad("Pick a living player.")
        if p["role"] == "mafia" and P[t]["role"] == "mafia":
            raise Bad("Mafia can't target their own.")
        if p["role"] == "detective" and t == pid:
            raise Bad("Investigate someone else.")
        n = room["night"]
        if p["role"] == "mafia":
            mafia_vote(room, pid, t)
        else:
            n[p["role"]] = t
        run_bots(room)
        return jsonify(ok=True)


@app.post("/api/vote")
def vote():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d)
        cast_vote(room, pid, d.get("target"))
        run_bots(room)
        return jsonify(ok=True)


@app.post("/api/chat")
def chat():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d)
        p = room["players"][pid]
        advance(room)
        text = " ".join(str(d.get("text", "")).split())[:200]
        if not text:
            raise Bad("Type a message first.")
        if time.time() - p.get("last", 0) < 0.8:
            raise Bad("Slow down a little.")
        p["last"] = time.time()
        ch = d.get("channel", "town")
        if ch not in ("town", "mafia"):
            raise Bad("Unknown chat channel.")
        if ch == "mafia":
            if p["role"] != "mafia" or not p["alive"] or room["phase"] not in ("day", "night"):
                raise Bad("Only living Mafia members can use Mafia chat.")
        elif room["phase"] not in ("day", "over"):
            raise Bad("Town chat opens during the day.")
        elif room["phase"] == "day" and not p["alive"]:
            raise Bad("Eliminated players can't chat.")
        if text.startswith("/"):
            cmd, _, arg = text[1:].partition(" ")
            cmd = cmd.lower()
            if ch == "mafia" and cmd in ("vote", "v"):
                mafia_vote(room, pid, find_player(room, arg))
            elif ch == "town" and room["phase"] == "day" and cmd == "skip":
                cast_vote(room, pid, "skip")
            elif ch == "town" and room["phase"] == "day" and cmd in ("vote", "v"):
                cast_vote(room, pid, find_player(room, arg))
            else:
                raise Bad("Commands: /vote name, or /skip (when voting is open).")
        else:
            chat_add(room, ch, p["name"], text)
        run_bots(room)
        return jsonify(ok=True)


@app.post("/api/skip")
def skip_discussion():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        if not room["players"][pid]["host"] or room["phase"] not in ("day", "night"):
            raise Bad("Only the host can skip a timer.")
        if room["phase"] == "night" and room["night_step"] == "mafia":
            raise Bad("The Mafia timer ends only after all Mafia vote or time runs out.")
        room["step_until" if room["phase"] == "night" else "discuss_until"] = 0
        run_bots(room)
        return jsonify(ok=True)


@app.post("/api/tally")
def force_tally():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        if not room["players"][pid]["host"] or room["phase"] != "day" or discussing(room):
            raise Bad("The host can end the vote once voting is open.")
        tally(room)
        run_bots(room)
        return jsonify(ok=True)


@app.post("/api/reset")
def reset():
    with lock:
        room, pid = ctx(request.get_json(force=True))
        if not room["players"][pid]["host"] or room["phase"] != "over":
            raise Bad("Only the host can restart.")
        room.update(phase="lobby", day=0, log=[], votes={}, winner=None, chat=[], said=set(), ended=False, death_events=[], story_used={})
        for p in room["players"].values():
            p.update(role=None, alive=True, notes=[], last=0)
        return jsonify(ok=True)


BASE = os.path.dirname(os.path.abspath(__file__))


@app.get("/")
def index():
    # Works whether index.html is in static/ or next to app.py
    for folder in (os.path.join(BASE, "static"), BASE):
        if os.path.isfile(os.path.join(folder, "index.html")):
            return send_from_directory(folder, "index.html")
    return "index.html is missing from the deployment.", 500


@app.get("/health")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
