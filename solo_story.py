"""Authored scenario canon and each character's limited private knowledge."""
import copy
import json
import random
import re
from pathlib import Path

SCENARIOS = tuple(json.loads((Path(__file__).parent / 'data/solo_scenarios.json').read_text()))


def choose(previous=None):
    return copy.deepcopy(random.choice([s for s in SCENARIOS if s['id'] != previous]))


def public_case(room):
    case = room.get('scenario')
    if not case:
        return None
    result = {key: case[key] for key in ('id', 'title', 'setting', 'anchor', 'pressure', 'opening')}
    result['cast'] = [dict(id=pid, name=p['name'], occupation=p['character']['occupation'],
                           description=p['character']['description'], relationship=p['character']['relationship'])
                      for pid, p in room['players'].items() if p.get('character')]
    if room['phase'] == 'over':
        result['epilogue'] = (
            f"The surviving witnesses set {case['anchor']} in the open. With the killers identified, they can guard the evidence together until help arrives. The danger was real; not every secret belonged to it."
            if room.get('winner') == 'town' else
            f"There are too few independent voices left to protect {case['anchor']}. The syndicate takes control of the room, and the account of what happened will belong to those who silence the others."
            if room.get('winner') == 'mafia' else
            "The inquiry is suspended before a verdict. The evidence remains, and so do the questions nobody has answered.")
    return result


def roleplay_reply(brain, context, pending, fallback):
    """Only this NPC's own background is available; roles never enter prose."""
    profile = context.get('character')
    if not profile:
        return fallback, False
    if not pending:
        return f"Before the first alarm: {profile['alibi']} {fallback}", False
    intent, message = pending['intent'], pending['message']
    if intent['addressed'] != context['self']:
        return fallback, False
    text, speaker = message['t'].casefold(), message['speaker']
    prefix = '@' + next(p['name'] for p in context['players'] if p['id'] == speaker) + ', '
    if re.search(r'\b(secret|hiding|hide|truth|honest|come clean)\b', text):
        questions = brain.setdefault('story_questions', {})
        questions[speaker] = questions.get(speaker, 0) + 1
        trusted = brain.get('story_trust', {}).get(speaker, 0) > 0
        if questions[speaker] > 1 or trusted:
            return prefix + profile['secret'] + " That is what I was hiding. It does not tell you who the killers are.", True
        return prefix + "I have something to lose besides my life. Ask me again if you mean to listen, not just find a name to condemn.", False
    if re.search(r'\b(where|alibi|when the alarm|first alarm)\b', text):
        return prefix + 'before the first alarm: ' + profile['alibi'] + ' That is my account; it is not independent proof.', False
    if re.search(r'\b(who are you|your work|your job|about yourself)\b', text):
        return prefix + "I am the " + profile['occupation'].lower() + ". Before the first alarm: " + profile['alibi'], False
    if re.search(r'\b(know|trust|relationship)\b', text) and intent['question']:
        return prefix + profile['relationship'] + ' That history may color my judgment; it does not prove a role.', False
    # Keep ordinary persuasion tied to the bot's beliefs, not canned exposition.
    return fallback, False


def death_story(room, name, cause):
    anchor = room['scenario']['anchor']
    if cause == 'vote':
        return f"{name} is removed from the discussion and placed under guard. With one voice fewer around {anchor}, the survivors must decide what their vote has actually proved."
    return f"At the next gathering, {name} does not answer. They are found dead before the group agrees what to do with {anchor}. An empty chair is left facing the evidence."
