"""Mafia — a Flask app where the server acts as the neutral Moderator.
State lives in memory, so run a single worker (see Procfile)."""
import math, os, random, re, secrets, string, threading, time, uuid
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, render_template_string, make_response, redirect
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape
from flask_compress import Compress
from death_stories import DEATH_STORIES, RESCUE_STORIES
import bot_brain
import solo_story

app = Flask(__name__, static_folder="static")
app.config.update(COMPRESS_ALGORITHM=["gzip"], COMPRESS_MIN_SIZE=500)
Compress(app)
# Railway injects its public domain; custom deployments can set SITE_URL.
app.config["SITE_URL"] = os.environ.get("SITE_URL") or (
    "https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"] if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else ""
)
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


def ctx(d, allow_friends=False):
    room = rooms.get(str(d.get("code", "")).strip().upper())
    viewer = d.get("pid")
    if not room:
        raise Bad("Room not found. It may have expired.", 404)
    if viewer in room["players"]:
        pid = viewer
    elif room.get('mode') == 'solo' and viewer in room.get('friends', {}):
        if not allow_friends:
            raise Bad("Only the lead Detective can use that control.", 403)
        pid = room['lead_pid']
    else:
        raise Bad("Room not found. It may have expired.", 404)
    room["t"] = time.time()
    return room, pid


def protected_player(room, pid):
    return room.get('mode') == 'solo' and pid == room.get('lead_pid')


def night_protected_player(room, pid):
    """Solo protection lifts on a decisive night without a living Mafia finding."""
    if not protected_player(room, pid):
        return False
    mafia = set(alive(room, 'mafia'))
    final_night = room['phase'] == 'night' and mafia and len(alive(room)) == 2 * len(mafia) + 1
    found = mafia & room['players'][pid].get('investigated', set())
    return not (final_night and not found)


def team_message(room, name, text, kind='msg'):
    room['team_seq'] = room.get('team_seq', 0) + 1
    room.setdefault('team_chat', []).append(dict(n=name, t=text, k=kind, seq=room['team_seq']))
    del room['team_chat'][:-100]


def clean(n):
    return " ".join(str(n or "").split())[:16]


def chat_add(room, ch, name, text, kind="msg", disclosure=False):
    room["chat_seq"] = room.get("chat_seq", 0) + 1
    speaker = next((pid for pid, p in room["players"].items() if p["name"] == name), None) if name else None
    room["chat"].append(dict(ch=ch, n=name, t=text, k=kind, seq=room["chat_seq"],
                             day=room.get("day", 0), speaker=speaker, disclosure=disclosure))
    del room["chat"][:-150]


def say(room, text):
    room["log"].append({"d": room["day"], "t": text})
    chat_add(room, "town", "", text, "sys")


def add_player(room, name, host=False, bot=False):
    if any(p["name"].lower() == name.lower() for p in room["players"].values()):
        raise Bad("That name is taken in this room.")
    pid = uuid.uuid4().hex
    room["players"][pid] = dict(name=name, role=None, alive=True, host=host, notes=[], bot=bot, score=0, pending_points=0, round_points=0, investigated=set(), investigation=None)
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
    room["discussion_ready"] = set()
    room["voting_announced"] = False
    room["night_step"], room["step_until"] = STEPS[0], time.time() + STEP


def advance(room):
    """Advance on confirmed actions, or keep the existing timeout fallback."""
    while room["phase"] == "night":
        role = room["night_step"]
        complete = (all(i in room["night"]["mafia"] for i in alive(room, "mafia"))
                    if role == "mafia" else bool(room["night"].get(role)) or not alive(room, role))
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

    if room["phase"] == "day" and not discussing(room) and not room.get("voting_announced"):
        room["voting_announced"] = True
        chat_add(room, "town", "", "Discussion is over. Voting is now open.", "sys")


def timers(room):
    now = time.time()
    if room["phase"] == "night":
        return math.ceil(max(0, room["step_until"] - now)), STEP
    if room["phase"] == "day":
        return math.ceil(max(0, room.get("discuss_until", 0) - now)), DISCUSS
    return 0, 0


def settle_scores(room):
    """Publish points once, only when a game ends; keep totals for this room."""
    if room.get("scores_settled"):
        return
    for player in room["players"].values():
        won = ((room.get("winner") == "mafia" and player["role"] == "mafia") or
               (room.get("winner") == "town" and player["role"] != "mafia" and player["alive"]))
        if player["role"] == "detective":
            points = 1 + int(bool(player.get("investigated"))) if won else 0
        else:
            points = player.get("pending_points", 0) + int(won)
        player["score"] = player.get("score", 0) + points
        player["round_points"] = points
        player["pending_points"] = 0
    room["scores_settled"] = True


def check_win(room):
    m = len(alive(room, "mafia"))
    t = len(alive(room)) - m
    w = "town" if m == 0 else "mafia" if m >= t else None
    if w:
        room["phase"], room["winner"] = "over", w
        settle_scores(room)
        say(room, "The town wins — every Mafia member is gone." if w == "town"
            else "The Mafia wins — they now match the town in numbers.")
    return bool(w)


def night_done(room):
    n = room["night"]
    return (all(i in n["mafia"] for i in alive(room, "mafia"))
            and (n["doctor"] or not alive(room, "doctor"))
            and (n["detective"] or not alive(room, "detective")))


def choose_death_background(room):
    """Use each installed illustration once per cycle, with no adjacent repeats."""
    folder = Path(app.static_folder) / "images" / "dead"
    pictures = {}
    for picture in sorted(folder.glob("*"), key=lambda p: p.suffix.lower() == ".webp"):
        if picture.is_file() and picture.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and all(c.isalnum() or c in "-_." for c in picture.name):
            pictures[picture.stem] = "/static/images/dead/" + picture.name
    available = sorted(pictures.values())
    if not available:
        return None
    used = room.setdefault("death_backgrounds_used", [])
    choices = [url for url in available if url not in used]
    if not choices:
        previous = used[-1] if used else None
        used.clear()
        choices = [url for url in available if url != previous] or available
    selected = choices[random.randrange(len(choices))]
    used.append(selected)
    return selected


def record_death(room, pid, cause):
    """Publish one shared story only when an elimination actually happens."""
    player = room["players"][pid]
    protected = night_protected_player(room, pid) if cause == 'night' else protected_player(room, pid)
    if not player["alive"] or protected:
        return
    player["alive"] = False
    player["death_background"] = choose_death_background(room)
    stories = DEATH_STORIES[cause]
    used = room.setdefault("story_used", {}).setdefault(cause, [])
    available = [i for i in range(len(stories)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(stories)))
    index = available[random.randrange(len(available))]
    used.append(index)
    tone, template = stories[index]
    story = (solo_story.death_story(room, player["name"], cause) if room.get("mode") == "solo"
             else template.format(name=player["name"]))
    if room.get("mode") == "solo":
        tone = "eerie"
    event = dict(id=uuid.uuid4().hex, day=room["day"], name=player["name"],
                 player_id=pid, cause=cause, tone=tone, story=story)
    room.setdefault("death_events", []).append(event)
    room.setdefault("notices", []).append(dict(event, kind="death"))
    say(room, story)


def record_rescue(room, pid):
    # No Doctor ID, name, pronouns or scoring information goes into public events.
    used = room.setdefault("story_used", {}).setdefault("rescue", [])
    available = [i for i in range(len(RESCUE_STORIES)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(RESCUE_STORIES)))
    index = available[random.randrange(len(available))]
    used.append(index)
    name = room["players"][pid]["name"]
    story = (f"{name} returns alive to the gathering. Someone intervened before the attack could become another empty chair. The evidence stays under watch; the protector stays unnamed."
             if room.get("mode") == "solo" else RESCUE_STORIES[index].format(name=name))
    event = dict(id=uuid.uuid4().hex, kind="rescue", day=room["day"], name=name,
                 player_id=pid, tone="hopeful", story=story)
    room.setdefault("notices", []).append(event)
    say(room, story)


def resolve_night(room):
    n, P = room["night"], room["players"]
    if n.get("resolved"):
        return
    n["resolved"] = True
    victim = n["victim"]
    if night_protected_player(room, victim):
        victim = n["victim"] = None
    if victim and victim != n["doctor"]:
        record_death(room, victim, "night")
        room["dawn"] = f"{P[victim]['name']} was killed."
    elif victim:
        for doctor in alive(room, "doctor"):
            P[doctor]["pending_points"] += 1
        record_rescue(room, victim)
        room["dawn"] = f"{P[victim]['name']} was saved by the Doctor. The Doctor's identity remains secret."
    else:
        room["dawn"] = "Nobody was killed last night."
    say(room, f"Night {room['day']}: {room['dawn']}")
    if not check_win(room):
        room["phase"] = "day"
        room["discuss_until"] = time.time() + DISCUSS


def tally(room):
    P, counts = room["players"], {}
    for t in room["votes"].values():
        if protected_player(room, t):
            continue
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
    if protected_player(room, t):
        raise Bad("The Detective team cannot be voted out in a solo story.")
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


def investigate(room, pid, target):
    """Keep one immediate investigation result private to its Detective."""
    p, suspect = room["players"][pid], room["players"][target]
    if room["night"]["detective"]:
        raise Bad("Your investigation is already confirmed for this night.")
    room["night"]["detective"] = target
    correct = suspect["role"] == "mafia"
    reminder = ("Do not directly reveal who the killer is. Convince the others through discussion and reasoning."
                if correct else "Keep investigating and listen to the town's discussion.")
    p["investigation"] = dict(id=uuid.uuid4().hex, day=room["day"], name=suspect["name"],
                              correct=correct, reminder=reminder)
    if p["bot"]:
        p.setdefault("brain", bot_brain.new_brain())["checks"][target] = correct
    if correct:
        p["investigated"].add(target)
    p["notes"].append(f"Night {room['day']}: {suspect['name']} is {'Mafia' if correct else 'not Mafia'}. {reminder}")


def proceed_to_vote(room, pid):
    if room["phase"] != "day" or not room["players"][pid]["alive"]:
        raise Bad("Only living players can proceed during discussion.")
    ready = room.setdefault("discussion_ready", set())
    if pid in ready:
        return  # Retries never duplicate a vote or chat update.
    if not discussing(room):
        raise Bad("Voting is already open.")
    ready.add(pid)
    chat_add(room, "town", "", f"{room['players'][pid]['name']} voted to proceed to voting ({len(ready)}/{len(alive(room))} ready).", "sys")
    if all(i in ready for i in alive(room)):
        room["discuss_until"] = 0


# The legacy skip route now casts the same individual readiness vote.
@app.post("/api/skip")
@app.post("/api/proceed")
def proceed():
    with lock:
        room, pid = ctx(request.get_json(force=True), allow_friends=True)
        advance(room)
        proceed_to_vote(room, pid)
        run_bots(room)
        return jsonify(ok=True)


def bot_context(room, pid):
    """Only public facts and the bot's own permitted team information."""
    player = room["players"][pid]
    return dict(self=pid, protected={room['lead_pid']} if room.get('mode') == 'solo' else set(), character=player.get("character"),
                relationships=player.get("relationships", {}),
                players=[dict(id=i, name=p["name"], alive=p["alive"], bot=p["bot"]) for i, p in room["players"].items()],
                allies={i for i in alive(room, "mafia")} if player["role"] == "mafia" else set(),
                votes=dict(room["votes"]))


def bot_discussion(room):
    if room.get('mode') == 'solo':
        return solo_story.discussion(room, lambda name, text, kind='msg': chat_add(room, 'town', name, text, kind))
    bots = [i for i in alive(room) if room["players"][i]["bot"]]
    now = time.time()
    contexts = {pid: bot_context(room, pid) for pid in bots}
    public = [c for c in room["chat"] if c["ch"] == "town" and c["k"] == "msg" and c.get("speaker")]
    latest_human = max((c['seq'] for c in public if not room["players"][c["speaker"]]["bot"] and c['day'] == room['day']), default=0)
    human_turn = latest_human > room.get("bot_human_replied", 0)

    def consume(pid):
        brain = room["players"][pid].setdefault("brain", bot_brain.new_brain())
        if brain['day'] != room['day']:
            brain.update(day=room['day'], posts=0, opened=False, pending=[], vote_version=None)
            eligible = [p['id'] for p in contexts[pid]['players'] if p['alive'] and p['id'] != pid and p['id'] not in contexts[pid]['allies']]
            brain['focus'] = random.choice(eligible) if eligible else None
        for message in public:
            if message['seq'] > brain['cursor'] and message['day'] == room['day']:
                bot_brain.hear(brain, message, contexts[pid])
        brain['cursor'] = room.get('chat_seq', 0)
        return brain

    for pid in bots:
        consume(pid)
    if not human_turn and now - room.get('bot_last_spoke', 0) < bot_brain.REPLY_DELAY:
        return False
    room['bot_human_replied'] = latest_human
    # At most two messages per turn; a human message can receive an immediate reply.
    candidates = []
    for pid in bots:
        brain = room['players'][pid]['brain']
        pending = max(brain['pending'], key=lambda p: (p['priority'], p['message']['seq']), default=None)
        interview = (pending and contexts[pid].get('character') and pending['intent']['addressed'] == pid
                     and not room['players'][pending['message']['speaker']]['bot'])
        limit = bot_brain.MAX_POSTS + (4 if interview else 0)
        if brain['posts'] >= limit:
            continue
        if pending or not brain['opened']:
            candidates.append((pending['priority'] if pending else 0, pid, pending))
    candidates.sort(key=lambda item: (-item[0], bots.index(item[1])))
    for _, pid, pending in candidates[:2]:
        brain = room['players'][pid]['brain']
        text = bot_brain.reply(brain, contexts[pid], pending)
        chat_add(room, 'town', room['players'][pid]['name'], text)
        brain['posts'] += 1
        brain['opened'] = True
        if pending:
            brain['pending'].remove(pending)
    if candidates:
        room['bot_last_spoke'] = now
        # Let every bot hear the replies before making a voting decision.
        public = [c for c in room['chat'] if c['ch'] == 'town' and c['k'] == 'msg' and c.get('speaker')]
        for pid in bots:
            consume(pid)
    return bool(candidates)


def run_bots(room):
    """Bots use bounded public conversation and private, role-legal knowledge."""
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
                    choices = [x for x in alive(room) if P[x]["role"] != "mafia" and not night_protected_player(room, x)]
                    target = solo_story.night_target(room, i, choices) if room.get('mode') == 'solo' else random.choice(choices)
                    mafia_vote(room, i, target)
                    moved = True
                elif r in ("doctor", "detective") and not n[r]:
                    choices = [x for x in alive(room) if x != i or r == "doctor"]
                    target = solo_story.night_target(room, i, choices) if room.get('mode') == 'solo' else random.choice(choices)
                    if r == "detective":
                        investigate(room, i, target)
                    else:
                        n[r] = target
                    moved = True
        elif room["phase"] == "day":
            moved = bot_discussion(room) or moved
            for i in alive(room):
                if discussing(room) and P[i]["bot"] and i not in room.get("discussion_ready", set()):
                    proceed_to_vote(room, i)
                    moved = True
            if not discussing(room):
                advance(room)
                for i in alive(room):
                    if room["phase"] != "day":
                        break
                    if P[i]["bot"]:
                        brain = P[i].setdefault('brain', bot_brain.new_brain())
                        public_messages = max((c.get('seq', 0) for c in room['chat'] if c['ch'] == 'town' and c['k'] == 'msg' and c.get('speaker')), default=0)
                        human_votes = tuple(sorted((voter, target) for voter, target in room['votes'].items() if not P[voter]['bot']))
                        version = (room['day'], public_messages, human_votes, len(room.get('story', {}).get('connections', {})))
                        if i not in room['votes'] or brain['vote_version'] != version:
                            brain['vote_version'] = version
                            target = solo_story.vote_target(room, i) if room.get('mode') == 'solo' else bot_brain.choose_target(brain, bot_context(room, i))
                            if room['votes'].get(i) != target:
                                cast_vote(room, i, target)
                                moved = True
                if room["phase"] == "day" and all(i in room["votes"] for i in alive(room)):
                    tally(room)
                    moved = True
        if not moved:
            break


def turn_background(room):
    """Only advertise installed artwork; retain phase colors otherwise."""
    scene = None
    if room["phase"] == "night":
        scene = {"mafia": "village", "doctor": "doctor", "detective": "detective"}.get(room["night_step"])
    elif room["phase"] == "day":
        scene = "discussion" if discussing(room) else "voting"
    if scene:
        for extension in ("webp", "jpg"):
            if (Path(app.static_folder) / "images" / "turns" / f"{scene}.{extension}").is_file():
                return f"/static/images/turns/{scene}.{extension}"
    return None


def view(room, pid):
    viewer = pid
    friend = room.get('friends', {}).get(viewer)
    if friend:
        pid = room['lead_pid']
    team_access = room.get('mode') == 'solo' and (viewer == room.get('lead_pid') or friend is not None)
    team = None
    if team_access:
        team = dict(cap=2, count=len(room['friends']), lead_name=room['players'][room['lead_pid']]['name'],
                    members=[dict(name=room['players'][room['lead_pid']]['name'], lead=True, you=viewer == room['lead_pid'])] +
                            [dict(name=f['name'], lead=False, you=viewer == fid) for fid, f in room['friends'].items()],
                    invite_path=(f"/?case={room['code']}&invite={room['invite_token']}" if not friend else None))
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
        players.append(dict(id=i, name=p["name"], protected=protected_player(room, i), bot=p["bot"], alive=p["alive"], host=p["host"], you=i == pid,
                            role=p["role"] if known else None, votes=vc.get(i, 0), score=p.get("score", 0),
                            round_points=p.get("round_points", 0) if over else 0))
    mode = None
    if room["phase"] == "day":
        mode = "town" if me["alive"] else None
    elif room["phase"] == "over":
        mode = "town"
    chat = [dict(c) for c in room["chat"] if c["ch"] == "town"][-80:]
    mafia_chat = [dict(c) for c in room["chat"] if c["ch"] == "mafia"][-80:] if me["role"] == "mafia" else []
    return dict(code=room["code"], team=team, team_chat=list(room.get("team_chat", [])) if team_access else [], mode=room.get("mode", "online"), scenario=solo_story.public_case(room), chat=chat, chat_mode=mode if not friend else None, phase=room["phase"], day=room["day"], winner=room.get("winner"),
                turn_background=turn_background(room), notices=room.get("notices", []), scores_settled=room.get("scores_settled", False),
                death_events=room.get("death_events", []), round_id=room.get("round_id"), settings=room["settings"], ended=room.get("ended", False), mafia_chat=mafia_chat,
                mafia_chat_open=me["role"] == "mafia" and me["alive"] and room["phase"] in ("day", "night"),
                discussion=dict(ready=len(set(alive(room)) & room.get("discussion_ready", set())),
                                total=len(alive(room)), voted=pid in room.get("discussion_ready", set())),
                investigation=me.get("investigation") if me["role"] == "detective" else None,
                min=MIN_PLAYERS, me=dict(name=friend["name"] if friend else me["name"], friend=bool(friend), role=me["role"], alive=me["alive"], host=me["host"] and not friend,
                                       at_risk=me['alive'] and protected_player(room, pid) and not night_protected_player(room, pid),
                                       death_background=me.get("death_background") if not me["alive"] else None),
                players=players, pick=pick, notes=me["notes"], mafia_picks=mp,
                skips=vc.get("skip", 0),
                timer_left=timers(room)[0], timer_total=timers(room)[1],
                night_step=room["night_step"] if room["phase"] == "night" else None,
                dawn=room.get("dawn") if room["phase"] == "day" else None, voting=room["phase"] == "day" and not discussing(room),
                votes_left=len(alive(room)) - len(room["votes"]) if room["phase"] == "day" else 0, log=room["log"][::-1][:40])


@app.post("/api/solo")
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
        room = rooms[code]
        pid = add_player(room, name, host=True)
        if request.path == '/api/solo':
            room['mode'] = 'solo'
            room.update(lead_pid=pid, friends={}, team_chat=[], invite_token=secrets.token_urlsafe(24))
            room['scenario'] = solo_story.choose(d.get('previous_scenario'))
            room['settings'] = dict(special_roles=True, mafia_count=1)
            for character in room['scenario']['cast']:
                if character['name'].casefold() == name.casefold():
                    room['scenario'] = solo_story.rename(room['scenario'], character['name'], character['name'] + ' Vale')
                    break
            for character in room['scenario']['cast']:
                npc = add_player(room, character['name'], bot=True)
                room['players'][npc]['character'] = dict(character)
            solo_story.initialize(room)
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
        if room.get("mode") == "solo":
            raise Bad("Ask the lead Detective for a solo invitation link, or choose Online play.")
        if room["phase"] != "lobby":
            raise Bad("That game has already started.")
        if len(room["players"]) >= MAX_PLAYERS:
            raise Bad("That room is full.")
        pid = add_player(room, name)
    return jsonify(code=room["code"], pid=pid)


@app.post('/api/solo-join')
def join_solo_team():
    d = request.get_json(force=True)
    name = clean(d.get('name'))
    if not name:
        raise Bad('Enter your name first.')
    with lock:
        room = rooms.get(str(d.get('code', '')).strip().upper())
        token = d.get('invite')
        if (not room or room.get('mode') != 'solo' or not isinstance(token, str) or not token.isascii()
                or not secrets.compare_digest(token, room['invite_token'])):
            raise Bad('This invitation is invalid or has expired.', 404)
        if len(room['friends']) >= 2:
            raise Bad('This Detective team already has two friends. The team is full.')
        names = [p['name'].casefold() for p in room['players'].values()] + [f['name'].casefold() for f in room['friends'].values()]
        if name.casefold() in names:
            raise Bad('That name is already in this case. Choose another alias.')
        fid = uuid.uuid4().hex
        room['friends'][fid] = dict(name=name, last=0)
        room['t'] = time.time()
        team_message(room, '', name + ' joined the Detective team.', 'sys')
        return jsonify(code=room['code'], pid=fid)


@app.post('/api/team-chat')
def detective_team_chat():
    d = request.get_json(force=True)
    with lock:
        room, pid = ctx(d, allow_friends=True)
        viewer = d.get('pid')
        if room.get('mode') != 'solo' or (viewer != room.get('lead_pid') and viewer not in room['friends']):
            raise Bad('This chat is only for the Detective team.', 403)
        text = ' '.join(str(d.get('text', '')).split())[:500]
        if not text:
            raise Bad('Type a message first.')
        author = room['friends'].get(viewer, room['players'][pid])
        if time.time() - author.get('team_last', 0) < 0.8:
            raise Bad('Slow down a little.')
        author['team_last'] = time.time()
        team_message(room, author['name'], text)
        return jsonify(ok=True)


@app.post("/api/state")
def state():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d, allow_friends=True)
        run_bots(room)
        return jsonify(view(room, d.get("pid")))


@app.post("/api/bot")
def bot():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d)
        if room.get("mode") == "solo":
            raise Bad("The cast is fixed for this story.")
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
        d = request.get_json(force=True)
        room, pid = ctx(d, allow_friends=True)
        viewer = d.get('pid')
        if viewer in room.get('friends', {}):
            member = room['friends'].pop(viewer)
            team_message(room, '', member['name'] + ' left the Detective team.', 'sys')
        elif room.get("mode") == "solo":
            del rooms[room["code"]]
        elif room["phase"] == "lobby":
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
        if room.get("mode") == "solo":
            raise Bad("Solo stories use one Detective, one Doctor, and exactly one Mafia.")
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
    if room.get('mode') == 'solo':
        # The culprit and Doctor belong to the authored case, so the evidence stays true.
        case = room['scenario']
        room['settings']['mafia_count'] = 1
        roles = ['detective' if not p['bot'] else
                 'mafia' if p['character']['key'] == case['culprit'] else
                 'doctor' if p['character']['key'] == case['doctor'] else 'town' for p in P.values()]
    else:
        sp = [r for k, r in enumerate(("doctor", "detective")) if room["settings"]["special_roles"] and n - m - k > 1]
        roles = ["mafia"] * m + sp + ["town"] * (n - m - len(sp))
        random.shuffle(roles)
    for p, r in zip(P.values(), roles):
        p.update(role=r, brain=bot_brain.new_brain(), alive=True, death_background=None, notes=[], last=0, pending_points=0, round_points=0, investigated=set(), investigation=None)
    room.update(day=0, log=[], winner=None, chat=[], chat_seq=0, bot_last_spoke=0, bot_human_replied=0, said=set(), ended=False, round_id=uuid.uuid4().hex, death_events=[], story_used={}, death_backgrounds_used=[], notices=[], scores_settled=False)
    if room.get('mode') == 'solo':
        solo_story.initialize(room)
        say(room, room['scenario']['title'] + ': ' + room['scenario']['pressure'])
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
        settle_scores(room)
        say(room, "The host ended the game. All roles are revealed.")
        return jsonify(ok=True)


def mafia_vote(room, pid, target):
    p = room["players"][pid]
    if room["phase"] != "night" or room["night_step"] != "mafia" or not p["alive"] or p["role"] != "mafia":
        raise Bad("Mafia kill voting is only open during the Mafia turn.")
    if target not in room["players"] or not room["players"][target]["alive"] or room["players"][target]["role"] == "mafia":
        raise Bad("Choose a living player outside the Mafia.")
    if night_protected_player(room, target):
        raise Bad("The Detective is protected unless this is a final-chance night with no surviving Mafia identified.")
    if pid in room["night"]["mafia"]:
        if room["night"]["mafia"][pid] == target:
            return
        raise Bad("Your Mafia target is already confirmed for this turn.")
    room["night"]["mafia"][pid] = target
    chat_add(room, "mafia", "", f"{p['name']} voted to kill {room['players'][target]['name']}.", "sys")


@app.post("/api/act")
def act():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d, allow_friends=True)
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
        elif p["role"] == "detective":
            investigate(room, pid, t)
        else:
            n[p["role"]] = t
        run_bots(room)
        return jsonify(ok=True)


@app.post("/api/vote")
def vote():
    with lock:
        d = request.get_json(force=True)
        room, pid = ctx(d, allow_friends=True)
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
        if room.get('mode') == 'solo':
            room['story']['feedback'] = ''
        run_bots(room)
        return jsonify(ok=True, feedback=room.get('story', {}).get('feedback', ''))


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
        if room.get('mode') == 'solo':
            solo_story.initialize(room)
        room.update(phase="lobby", day=0, log=[], votes={}, discussion_ready=set(), voting_announced=False, winner=None, chat=[], said=set(), ended=False, death_events=[], story_used={}, death_backgrounds_used=[], notices=[], scores_settled=False)
        for p in room["players"].values():
            p.update(role=None, brain=bot_brain.new_brain(), alive=True, death_background=None, notes=[], last=0, pending_points=0, round_points=0, investigated=set(), investigation=None)
        return jsonify(ok=True)


@app.after_request
def deliver_response(response):
    # send_file streams bypass compression by default; these small text files
    # can be buffered so gzip validators and conditional requests remain valid.
    if response.status_code == 200 and response.mimetype in ("text/html", "text/css", "text/javascript", "application/javascript"):
        response.direct_passthrough = False
        stream = response.response
        body = response.get_data()
        if hasattr(stream, "close"):
            stream.close()
        response.set_data(body)
    if request.path.startswith("/api/"):
        # Return the caller's authorized view with an action to avoid a second RTT.
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        data = request.get_json(silent=True) or {}
        if response.status_code == 200 and request.path != "/api/state" and data.get("include_state"):
            payload = response.get_json(silent=True)
            if isinstance(payload, dict):
                code = str(payload.get("code", data.get("code", ""))).strip().upper()
                pid = payload.get("pid", data.get("pid"))
                with lock:
                    room = rooms.get(code)
                    if room and (pid in room["players"] or pid in room.get("friends", {})):
                        payload["state"] = view(room, pid)
                        response.set_data(app.json.dumps(payload))
    elif request.path.startswith("/static/") and Path(request.path).suffix.lower() in (".webp", ".png", ".jpg", ".jpeg", ".ttf", ".woff2", ".mp3"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        # Revalidate HTML, scripts and styles so deployments are picked up promptly.
        response.headers["Cache-Control"] = "no-cache"
    return response


BASE = os.path.dirname(os.path.abspath(__file__))


def public_site_url():
    """Use deployment configuration, never an untrusted request Host header."""
    value = app.config.get("SITE_URL", "").strip().rstrip("/")
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if (parsed.scheme not in ("https", "http") or not parsed.netloc
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        return ""
    return value


def game_schema(site_url):
    schema = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "Mafia · After dark",
        "applicationCategory": "GameApplication",
        "operatingSystem": "Any",
        "browserRequirements": "Requires JavaScript and an internet connection",
        "inLanguage": "en",
        "description": "A free online Mafia social deduction party game for 3–20 players, with private rooms, optional bots, and Doctor and Detective roles.",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }
    if site_url:
        schema.update(url=site_url + "/", image=site_url + "/static/images/opening/town.png")
    return schema


@app.get("/")
def index():
    # Render the same useful public introduction for players and search engines.
    for folder in (os.path.join(BASE, "static"), BASE):
        path = Path(folder) / "index.html"
        if path.is_file():
            site_url = public_site_url()
            response = make_response(render_template_string(
                path.read_text(), site_url=site_url, game_schema=game_schema(site_url)))
            response.add_etag()
            return response.make_conditional(request)
    return "index.html is missing from the deployment.", 500


@app.get("/index.html")
@app.get("/static/index.html")
def duplicate_index():
    return redirect("/", code=301)


@app.get("/robots.txt")
def robots():
    body = "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /health\n"
    if public_site_url():
        body += "Sitemap: " + public_site_url() + "/sitemap.xml\n"
    return app.response_class(body, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    site_url = public_site_url()
    if not site_url:
        response = app.response_class("Set SITE_URL to the public site origin to enable the sitemap.\n", status=503, mimetype="text/plain")
        response.headers["X-Robots-Tag"] = "noindex"
        return response
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><loc>' + xml_escape(site_url + "/") + '</loc></url></urlset>')
    return app.response_class(body, mimetype="application/xml")


@app.get("/health")
def health():
    response = make_response("ok")
    response.headers["X-Robots-Tag"] = "noindex"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
