"""Seven authored mysteries with persistent testimony and evidence-driven actors.

The narrator owns canon. NPC decisions use published evidence and player claims,
never the solution or another character's hidden role. No online dialogue is used.
"""
import copy
import json
import random
import re
from pathlib import Path
import case_details

SCENARIOS = tuple(json.loads((Path(__file__).parent / 'data/solo_scenarios.json').read_text()))
QUESTIONS = (
    dict(id='detail', label='What detail did you leave out?'),
    dict(id='motive', label='Why did you hold that back?'),
    dict(id='correction', label='What would you correct in your account?'),
)


def catalog():
    return [dict(id=case['id'], title=case['title'], setting=case['setting'],
                 pressure=case['pressure'], complexity=case_details.complexity(case),
                 origin=copy.deepcopy(case.get('origin', {}))) for case in SCENARIOS]


def choose(previous=None, selected=None):
    if selected and selected != 'random':
        case = next((case for case in SCENARIOS if case['id'] == selected), None)
        if not case:
            raise ValueError('Choose a story from the list, or select Random.')
        return copy.deepcopy(case)
    return copy.deepcopy(random.choice([case for case in SCENARIOS if case['id'] != previous]))


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
    room['story'] = dict(revealed={}, connections={}, said=set(), claims={}, chapters=[], day=0,
                         question_round=None, question_target=None, question_id=None, statements={},
                         account_rounds={}, revisions=[], feedback='')


def question_state(room):
    story = room.get('story', {})
    used = story.get('question_round') == room['day']
    target = room['players'].get(story.get('question_target'), {}) if used else {}
    return dict(round=room['day'], used=used, target_name=target.get('name'),
                question_id=story.get('question_id') if used else None,
                choices=[dict(choice) for choice in QUESTIONS])


def question_clue(room, pid, question):
    profile = room['players'][pid]['character']
    kind = {'detail': 'observation', 'motive': 'admission', 'correction': 'correction'}[question]
    if kind != 'correction':
        return next(c for c in room['scenario']['clues'] if c['source'] == profile['key'] and c['kind'] == kind)
    return dict(id=profile['key'] + '-correction', source=profile['key'], kind='correction', day=1,
                title=profile['name'] + ' · Correction', text=profile.get('correction', profile['defense']))


def question_options(room, pid):
    story = room.get('story', {})
    phase_open = room['phase'] == 'day' and not room.get('solo_voting', False)
    result = []
    for choice in QUESTIONS:
        clue = question_clue(room, pid, choice['id'])
        reason = ('The witness is no longer available.' if not room['players'][pid]['alive'] else
                  'Questions open during the round discussion.' if not phase_open else
                  'Your team has already asked its one question this round.' if question_state(room)['used'] else
                  'This answer is already recorded in your journal.' if clue['id'] in story.get('revealed', {}) else '')
        result.append(dict(choice, available=not reason, reason=reason))
    return result


def cast_ids(room):
    return {p['character']['key']: pid for pid, p in room['players'].items() if p.get('character')}


def public_case(room):
    case = room.get('scenario')
    if not case:
        return None
    story = room.get('story', {})
    result = {key: case[key] for key in ('id', 'title', 'setting', 'anchor', 'pressure', 'opening')}
    result['origin'] = copy.deepcopy(case.get('origin', {}))
    result['complexity'] = case_details.complexity(case)
    result['influence_feedback'] = copy.deepcopy(story.get('last_influence'))
    if room.get('tutorial'):
        ids = cast_ids(room)
        result['tutorial_guidance'] = dict(question_target=ids.get('mara'), question='detail',
                                            suspect_target=ids.get('ellis'))
    result['interrogation'] = question_state(room)
    result['revisions'] = list(story.get('revisions', []))
    result['cast'] = [dict(id=pid, name=p['name'], occupation=p['character']['occupation'],
                           description=p['character']['description'], relationship=p['character']['relationship'],
                           alive=p['alive'], topics=p['character']['topics'],
                           statement=story.get('statements', {}).get(pid),
                           question_options=question_options(room, pid))
                      for pid, p in room['players'].items() if p.get('character')]
    result['journal'] = list(story.get('revealed', {}).values())
    result['connections'] = list(story.get('connections', {}).values())
    result['chapters'] = list(story.get('chapters', []))
    if room['phase'] == 'over':
        winner = room.get('winner')
        result['epilogue'] = (case['ending_win'] if winner == 'town' else case['ending_loss'] if winner == 'mafia'
                              else 'The inquiry is suspended. The signed accounts remain in the file, but there is no verdict.')
        result['solution'] = case['solution']
        result['timeline'] = case['timeline']
        result['reconstruction'] = list(case.get('reconstruction', [case['solution']]))
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
        return True
    return False


def ask_question(room, target, question, publish):
    if room['phase'] != 'day' or room.get('solo_voting', False):
        raise ValueError('Ask your one question during the round discussion, before proceeding to vote.')
    if question not in {choice['id'] for choice in QUESTIONS}:
        raise ValueError('Choose one of the three questions.')
    if target not in room['players'] or not room['players'][target].get('character') or not room['players'][target]['alive']:
        raise ValueError('Choose a living witness.')
    story = room['story']
    if question_state(room)['used']:
        raise ValueError('Your team can ask only one question to one witness in this round.')
    clue = question_clue(room, target, question)
    if clue['id'] in story['revealed']:
        raise ValueError('This answer is already recorded. Choose a question with a new answer.')
    # Room lock in the API makes the shared team quota and statement revision atomic.
    story.update(question_round=room['day'], question_target=target, question_id=question)
    before = story['statements'].get(target, room['players'][target]['character']['account'])
    reveal(room, clue, publish)
    after = (clue['text'] if question == 'correction' else before + '\nAdditional testimony: ' + clue['text'])
    story['statements'][target] = after
    story['revisions'].append(dict(round=room['day'], name=room['players'][target]['name'],
        target=target, question=next(choice['label'] for choice in QUESTIONS if choice['id'] == question),
        before=before, after=after, response=clue['text']))
    while connect(room, publish):
        pass


def influence(room, lead, target, stance, publish):
    if room['phase'] != 'day' or room.get('solo_voting', False):
        raise ValueError('Influence the witnesses during discussion, before proceeding to vote.')
    if target not in room['players'] or not room['players'][target].get('character') or not room['players'][target]['alive']:
        raise ValueError('Choose a living witness.')
    if stance not in ('suspect', 'defend', 'neutral'):
        raise ValueError('Choose Suspect, Defend, or Withdraw.')
    claims = room['story']['claims']
    previous = claims.get((lead, target))
    value = {'suspect': 2, 'defend': -2, 'neutral': None}[stance]
    # Compare the same public-evidence decisions the witnesses use at the ballot.
    # These are current preferences, never a promise about a later final vote.
    def preferences():
        return [dict(name=p['name'], target=vote_target(room, pid))
                for pid, p in room['players'].items() if p.get('character') and p['alive']]

    before = preferences()
    name = room['players'][target]['name']
    if value == previous:
        result = dict(status='unchanged', target=target, target_name=name, stance=stance,
                      changed_witnesses=[], before=before, after=before,
                      message='This position is already recorded. Repeating it does not add influence or change current voting preferences.')
        room['story']['last_influence'] = result
        return copy.deepcopy(result)
    if value is None:
        claims.pop((lead, target), None)
    else:
        claims[(lead, target)] = value
    text = {'suspect': f'The Detective team asks the witnesses to consider a case against {name}.',
            'defend': f'The Detective team speaks in defense of {name}.',
            'neutral': f'The Detective team withdraws its position on {name}.'}[stance]
    publish('', text, 'sys')
    after = preferences()
    changed = [new['name'] for old, new in zip(before, after) if old['target'] != new['target']]
    message = (f"Position recorded. {len(changed)} witness{'es' if len(changed) != 1 else ''} changed their current voting preference. "
               'These are intentions; new evidence can change the final ballot.' if changed else
               'Position recorded, but no witness changed their current voting preference. Compare supporting evidence in the journal; an unsupported accusation alone is not enough.')
    result = dict(status='accepted', target=target, target_name=name, stance=stance,
                  changed_witnesses=changed, before=before, after=after, message=message)
    room['story']['last_influence'] = result
    return copy.deepcopy(result)


def evidence(room, action, publish):
    if room['phase'] != 'day':
        raise ValueError('Inspect and compare evidence during the day.')
    if action == 'inspect':
        for clue in room['scenario']['clues']:
            if clue['kind'] == 'document' and reveal(room, clue, publish):
                while connect(room, publish):
                    pass
                return
        ids = cast_ids(room)
        for clue in room['scenario']['clues']:
            if (clue['kind'] == 'observation' and not room['players'][ids[clue['source']]]['alive']
                    and reveal(room, clue, publish)):
                while connect(room, publish):
                    pass
                return 'Recovered a missing witness’s sealed pre-watch observation.'
        return 'All scene exhibits and available sealed notes are already recorded in the journal.'

    if action == 'compare':
        if not connect(room, publish):
            return 'No new comparison is supported yet. Read the accounts, inspect the scene, or use your one question.'
        while connect(room, publish):
            pass
        return
    raise ValueError('Choose Inspect the scene or Compare accounts.')


def discussion(room, publish):
    """One account per living witness per round; polling has no narrative side effects."""
    if room['phase'] != 'day':
        return False
    if 'story' not in room:
        initialize(room)
    story, case = room['story'], room['scenario']
    if story['day'] == room['day']:
        return False
    story['day'] = room['day']
    index = room['day'] - 1
    if index < len(case['chapters']):
        title, text = case['chapters'][index]
        story['chapters'].append(dict(day=room['day'], title=title, text=text))
        publish('', title + ': ' + text, 'sys')
    ids = cast_ids(room)
    accounts = story['account_rounds'].setdefault(room['day'], {})
    # Add one fresh pre-watch detail to this round's account, not a second speech.
    for clue in case['clues']:
        if clue['kind'] == 'observation' and clue['id'] not in story['revealed']:
            pid = ids[clue['source']]
            if reveal(room, clue, lambda *args: None):
                before = story['statements'].get(pid, room['players'][pid]['character']['account'])
                story['statements'][pid] = before + '\nAdditional testimony: ' + clue['text']
                break
    for clue in case['clues']:
        if clue['kind'] != 'account':
            continue
        pid = ids[clue['source']]
        if not room['players'][pid]['alive']:
            reveal(room, clue, publish)
            continue
        text = story['statements'].setdefault(pid, clue['text'])
        accounts[pid] = text
        reveal(room, clue, lambda *args: None)
        publish(room['players'][pid]['name'], text, 'msg')
    while connect(room, publish):
        pass
    return True


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
    return case_details.death_story(room, name, cause)
