"""Seven authored mysteries with persistent testimony and evidence-driven actors.

The narrator owns canon. NPC decisions use published evidence and player claims,
never the solution or another character's hidden role. No online dialogue is used.
"""
import copy
import json
import random
import re
import time
from pathlib import Path
from bot_brain import read_message

SCENARIOS = tuple(json.loads((Path(__file__).parent / 'data/solo_scenarios.json').read_text()))
REPLY_DELAY = 4


def choose(previous=None):
    return copy.deepcopy(random.choice([s for s in SCENARIOS if s['id'] != previous]))


def rename(case, old, new):
    """Keep every account consistent when a player's alias collides with a cast name."""
    if isinstance(case, str):
        return re.sub(r'\b' + re.escape(old) + r'\b', lambda _: new, case)
    if isinstance(case, list):
        return [rename(value, old, new) for value in case]
    if isinstance(case, dict):
        return {key: rename(value, old, new) for key, value in case.items()}
    return case


def initialize(room):
    room['story'] = dict(revealed={}, connections={}, said=set(), cursor=0, last_spoke=0,
                         asks={}, trust={}, claims={}, chapters=[], day=0, auto={}, feedback='')


def cast_ids(room):
    return {p['character']['key']: pid for pid, p in room['players'].items() if p.get('character')}


def public_case(room):
    case = room.get('scenario')
    if not case:
        return None
    story = room.get('story', {})
    result = {key: case[key] for key in ('id', 'title', 'setting', 'anchor', 'pressure', 'opening')}
    result['cast'] = [dict(id=pid, name=p['name'], occupation=p['character']['occupation'],
                           description=p['character']['description'], relationship=p['character']['relationship'],
                           alive=p['alive'], topics=p['character']['topics'])
                      for pid, p in room['players'].items() if p.get('character')]
    result['journal'] = list(story.get('revealed', {}).values())
    result['connections'] = list(story.get('connections', {}).values())
    result['chapters'] = list(story.get('chapters', []))
    if room['phase'] == 'over':
        winner = room.get('winner')
        result['epilogue'] = (case['ending_win'] if winner == 'town' else case['ending_loss'] if winner == 'mafia'
                              else 'The inquiry is suspended. The signed accounts remain in the file, but there is no verdict.')
        if winner:
            result['solution'] = case['solution']
            result['timeline'] = case['timeline']
            lost = [p['name'] for p in room['players'].values() if p.get('character') and not p['alive']]
            result['consequences'] = (
                ('Absent from the final gathering: ' + ', '.join(lost) + '. ' if lost else 'Every witness remains at the table. ')
                + f"Your file preserves {len(result['journal'])} accounts and exhibits, with {len(result['connections'])} comparisons made before the verdict.")
    return result


def say_once(room, publish, key, name, text, kind='msg'):
    story = room['story']
    if key in story['said']:
        return False
    story['said'].add(key)
    publish(name, text, kind)
    return True


def reveal(room, clue, publish):
    story = room['story']
    if clue['id'] in story['revealed'] or clue['day'] > room['day']:
        return False
    pid = cast_ids(room).get(clue['source'])
    player = room['players'].get(pid)
    archived = player is not None and not player['alive']
    # A personal admission is not conveniently discovered in a dead person's notes.
    if archived and clue['kind'] == 'admission':
        return False
    name = player['name'] if player else 'Scene inspection'
    entry = dict(id=clue['id'], title=clue['title'], kind=clue['kind'], text=clue['text'],
                 source=name, day=room['day'], archived=archived)
    story['revealed'][clue['id']] = entry
    if archived:
        publish('', f"From {name}’s sealed pre-watch notes: {clue['text']}", 'sys')
    elif player:
        publish(name, clue['text'], 'msg')
    else:
        publish('', clue['title'] + ': ' + clue['text'], 'sys')
    return True


def connect(room, publish):
    """A comparison is available only after every supporting item is public."""
    story, ids = room['story'], cast_ids(room)
    for link in room['scenario']['connections']:
        if link['id'] in story['connections'] or not set(link['requires']) <= story['revealed'].keys():
            continue
        speaker = room['players'][ids[link['speaker']]]
        subject = room['players'][ids[link['subject']]]
        if speaker['alive'] and subject['alive']:
            publish(speaker['name'], link['text'], 'msg')
        else:
            # Do not put a newly composed accusation in the mouth of a dead NPC.
            sources = ', '.join(story['revealed'][key]['title'] for key in link['requires'])
            publish('', 'The file now allows a comparison: ' + sources + '. Read these accounts together.', 'sys')
        story['connections'][link['id']] = dict(id=link['id'], title='Compare: ' + subject['name'],
            sources=list(link['requires']), text=link['text'] if speaker['alive'] and subject['alive'] else
            'These recorded accounts concern ' + subject['name'] + '. Their sources remain in the journal.',
            day=room['day'])
        if subject['alive']:
            say_once(room, publish, 'reply:' + link['id'], subject['name'], link['reply'])
        return True
    return False


def interview(room, pid, text, intent, publish):
    """Bounded, authored answers; repeat requests consult memory rather than reprint."""
    player, story = room['players'][pid], room['story']
    profile = player.get('character')
    if not profile:
        return False
    key = profile['key']
    clues = {c['kind']: c for c in room['scenario']['clues'] if c['source'] == key}
    text = text.casefold()
    if re.search(r'\b(secret|hiding|hide|truth|honest|motive|come clean)\b', text):
        if not player['alive']:
            story['feedback'] = 'That witness cannot be questioned. Their recorded account and observations remain available.'
            return False
        story['asks'][pid] = story['asks'].get(pid, 0) + 1
        if story['trust'].get(pid, 0) > 0 or story['asks'][pid] >= 2:
            return reveal(room, clues['admission'], publish)
        return say_once(room, publish, 'defense:' + key, player['name'], profile['defense'])
    if re.search(r'\b(where|alibi|account|what happened|timeline|notes)\b', text):
        return reveal(room, clues['account'], publish)
    if (re.search(r'\b(see|saw|hear|heard|notice|noticed|evidence|remember|detail|clue|why)\b', text)
            or any(re.search(r'\b' + re.escape(topic) + r'\b', text) for topic in profile['topics'])):
        return reveal(room, clues['observation'], publish)
    if intent['stances'].get(pid, 0) > 0 and player['alive']:
        return say_once(room, publish, 'defense:' + key, player['name'], profile['defense'])
    if intent['stances'].get(pid, 0) < 0:
        return reveal(room, clues['observation'], publish)
    return False


def respond(room, message, publish):
    story = room['story']
    roster = [dict(id=pid, name=p['name']) for pid, p in room['players'].items()]
    intent = read_message(message['t'], roster)
    for target, stance in intent['stances'].items():
        if target in room['players'] and room['players'][target].get('character'):
            story['claims'][(message['speaker'], target)] = stance
            story['trust'][target] = 1 if stance < 0 else -1
    addressed = intent['addressed']
    if not addressed and len(intent['mentions']) == 1:
        addressed = intent['mentions'][0]
    if addressed:
        return interview(room, addressed, message['t'], intent, publish)
    text = message['t'].casefold()
    if re.search(r'\b(compare|contradict|inconsistent|disagree|match)\b', text):
        return connect(room, publish)
    if re.search(r'\b(search|inspect|examine|check|look)\b', text):
        documents = [c for c in room['scenario']['clues'] if c['kind'] == 'document']
        matched = [c for c in documents if any(re.search(r'\b' + re.escape(topic) + r'\b', text) for topic in c['topics'])]
        for clue in matched or documents:
            if reveal(room, clue, publish):
                return True
        return False
    if intent['question']:
        ids = cast_ids(room)
        for clue in room['scenario']['clues']:
            if (clue['kind'] == 'observation' and room['players'][ids[clue['source']]]['alive']
                    and any(re.search(r'\b' + re.escape(topic) + r'\b', text) for topic in clue['topics'])):
                if reveal(room, clue, publish):
                    return True
    # Multiple named accusations still affect votes, even without an addressed reply.
    return False


def discussion(room, publish):
    if room['phase'] != 'day':
        return False
    if 'story' not in room:
        initialize(room)
    story, case = room['story'], room['scenario']
    now = time.time()
    if story['day'] != room['day']:
        story['day'] = room['day']
        index = room['day'] - 1
        if index < len(case['chapters']):
            title, text = case['chapters'][index]
            story['chapters'].append(dict(day=room['day'], title=title, text=text))
            publish('', title + ': ' + text, 'sys')
    messages = [c for c in room['chat'] if c['ch'] == 'town' and c['k'] == 'msg'
                and c.get('speaker') in room['players'] and not room['players'][c['speaker']]['bot']
                and c['seq'] > story['cursor']]
    if messages:
        # Each message is consumed once, including across day boundaries.
        moved = False
        for message in messages:
            story['cursor'] = max(story['cursor'], message['seq'])
            story['feedback'] = ''
            answered = respond(room, message, publish)
            moved = answered or moved
            if not answered and not story['feedback']:
                story['feedback'] = 'No new testimony. Check the case journal, ask about another detail, or compare the accounts you have collected.'
        # A witness may answer another witness's newly published evidence immediately.
        moved = connect(room, publish) or moved
        story['last_spoke'] = now
        return moved
    if now - story['last_spoke'] < REPLY_DELAY:
        return False
    story['last_spoke'] = now
    if connect(room, publish):
        return True
    ids = cast_ids(room)
    # First accounts are never reissued at dawn. Inactive witnesses do not chat.
    for clue in case['clues']:
        if clue['kind'] == 'account' and room['players'][ids[clue['source']]]['alive']:
            if reveal(room, clue, publish):
                return True
    # Only two fresh unsolicited observations per day; questions drive the rest.
    count = story['auto'].get(room['day'], 0)
    if count < 2:
        for clue in case['clues']:
            if clue['kind'] == 'observation' and room['players'][ids[clue['source']]]['alive']:
                if reveal(room, clue, publish):
                    story['auto'][room['day']] = count + 1
                    return True
    return False


def suspicion(room, pid):
    """Only public comparisons and the human team's stated claims affect ballots."""
    story, ids = room.get('story', {}), cast_ids(room)
    scores = {target: 0.0 for target, p in room['players'].items()
              if p['alive'] and p.get('character') and target != pid}
    for link in room['scenario']['connections']:
        if link['id'] in story.get('connections', {}):
            target = ids[link['subject']]
            if target in scores:
                scores[target] += link['effect']
    for (_, target), value in story.get('claims', {}).items():
        if target in scores:
            scores[target] += value * 0.8
    return scores


def vote_target(room, pid):
    scores = suspicion(room, pid)
    if not scores or max(scores.values()) < 2.5:
        return 'skip'
    best = max(scores.values())
    return next(target for target, value in scores.items() if value == best)


def night_target(room, pid, choices):
    """React to public disclosure: the killer silences an active corroborator."""
    story, ids = room.get('story', {}), cast_ids(room)
    if room['players'][pid]['role'] == 'mafia':
        pressure = {target: 0 for target in choices}
        for clue in room['scenario']['clues']:
            source = ids.get(clue['source'])
            if clue['id'] in story.get('revealed', {}) and source in pressure:
                pressure[source] += 1
        for link in room['scenario']['connections']:
            source = ids[link['speaker']]
            if link['id'] in story.get('connections', {}) and ids[link['subject']] == pid and source in pressure:
                pressure[source] += 3
        highest = max(pressure.values(), default=0)
        return random.choice([target for target in choices if pressure[target] == highest])
    # The Doctor can guard a publicly exposed witness without knowing the killer.
    speakers = [ids[link['speaker']] for link in room['scenario']['connections']
                if link['id'] in story.get('connections', {}) and ids[link['speaker']] in choices]
    return random.choice(speakers or choices)


def death_story(room, name, cause):
    anchor = room['scenario']['anchor']
    if cause == 'vote':
        return f"{name} is placed under guard and loses access to {anchor}. Their signed account stays in your file; their voice is missing from the next discussion."
    return f"{name} does not return from the watch. When the body is found, you secure their sealed pre-watch notes beside {anchor}. What was never written down can no longer be asked."
