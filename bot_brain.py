"""Small, local social-deduction agents. Inputs contain no other players' roles.

This is deliberately bounded, rule-based dialogue rather than an LLM. Human
claims carry more weight than bot chatter, duplicate claims replace each other,
and a bot's own investigation can override hearsay without being announced.
"""
import hashlib
import re

MAX_POSTS = 6
REPLY_DELAY = 4


def new_brain():
    return dict(claims={}, checks={}, cursor=0, pending=[], day=0, posts=0,
                focus=None, opened=False, vote_version=None, claim_basis={})


def mentions(text, players):
    """Match full aliases (including spaces), never ambiguous name prefixes."""
    alternatives = '|'.join(re.escape(p['name']) for p in sorted(players, key=lambda p: len(p['name']), reverse=True))
    if not alternatives:
        return []
    names = {p['name'].casefold(): p['id'] for p in players}
    pattern = re.compile(r'(?<!\w)@?(' + alternatives + r')(?!\w)', re.I)
    return [(m.start(), m.end(), names[m.group(1).casefold()]) for m in pattern.finditer(text)]


def read_message(text, players):
    """Understand a few ordinary accusations, defenses, and questions."""
    text = text.replace('’', "'")
    found = mentions(text, players)
    stances = {}
    question = '?' in text or bool(re.search(r'\b(why|explain|what evidence)\b', text, re.I))
    for index, (start, end, target) in enumerate(found):
        # Do not let a verb for one alias attach to a later alias.
        previous = found[index - 1][1] if index else 0
        following = found[index + 1][0] if index + 1 < len(found) else len(text)
        before = re.split(r'[,.!;:]|\b(?:but|instead)\b', text[previous:start].casefold())[-1].strip()
        after = re.split(r'[,.!?;:]|\b(?:but|instead)\b', text[end:following].casefold())[0].strip()
        delimiter = re.search(r'[,.!?;:]', text[end:following])
        if re.search(r'\b(?:why|explain|what evidence|do you|should we)\b', before) or (delimiter and delimiter.group() == '?'):
            continue
        if re.search(r"(?:don't|do not|dont)\s+trust\s*$", before):
            stances[target] = 2
        elif (re.search(r"(?:don't|do not|dont)\s+(?:vote(?: for)?|suspect|accuse)\s*$", before)
                or re.search(r'\b(?:trust|defend|believe in)\s*$', before)
                or re.match(r"(?:is |seems |looks )?(?:not (?:the )?mafia|innocent|safe|not suspicious)\b", after)):
            stances[target] = -2
        elif (re.search(r'\b(?:suspect|accuse|vote(?: for)?|lean (?:towards|toward)|suspicious of)\s*$', before)
                or re.match(r'(?:is |seems |looks |might be |could be )(?:the )?(?:mafia|suspicious|a killer)\b', after)):
            stances[target] = 2
    addressed = None
    if found:
        start, end, target = found[0]
        if (text[start:start + 1] == '@' or not text[:start].strip()) and re.match(r'\s*[,!:]', text[end:]):
            addressed = target
    return dict(stances=stances, question=question, mentions=[target for _, _, target in found], addressed=addressed)


def hear(brain, message, context):
    interpretation = read_message(message['t'], context['players'])
    speaker = message['speaker']
    if message.get('disclosure'):
        brain.setdefault('disclosed', set()).add(speaker)
    if interpretation['stances'].get(context['self'], 0) < 0:
        brain.setdefault('story_trust', {})[speaker] = 1
    if speaker == context['self']:
        return
    # A bot's new stated preference replaces its previous accusation. Human
    # players may intentionally suspect more than one person.
    positive = {target for target, stance in interpretation['stances'].items() if stance > 0}
    speaker_is_bot = any(p['id'] == speaker and p['bot'] for p in context['players'])
    provisional = speaker_is_bot and bool(re.search(
        r'\b(?:lean(?:ing)? (?:towards|toward)|hunch|my own read)\b', message['t'], re.I))
    if speaker_is_bot and positive:
        brain['claims'] = {key: value for key, value in brain['claims'].items()
                           if key[0] != speaker or value < 0 or key[1] in positive}
    for target, stance in interpretation['stances'].items():
        # Each speaker has at most one current claim per target, across days.
        brain['claims'][(speaker, target)] = stance
        brain.setdefault('claim_basis', {})[(speaker, target)] = 'hunch' if provisional else 'assertion'
    relevant = interpretation['addressed'] == context['self'] or context['self'] in interpretation['stances']
    if relevant or interpretation['stances'] or interpretation['question']:
        brain['pending'].append(dict(message=message, intent=interpretation, priority=3 if relevant else 1))
        brain['pending'] = brain['pending'][-4:]


def scores(brain, context):
    players = {p['id']: p for p in context['players']}
    totals = {pid: 0.0 for pid, p in players.items() if p['alive']}
    # Judge trust only against this bot's own permitted knowledge.
    verified = {}
    for (author, target), value in brain['claims'].items():
        if target in brain['checks']:
            verified.setdefault(author, []).append((value > 0) == brain['checks'][target])
    bot_claims = {}
    for (speaker, target), stance in brain['claims'].items():
        if speaker not in players or target not in totals:
            continue
        trust = (1.4 if all(verified[speaker]) else 0.25) if speaker in verified else 1.0
        if players[speaker]['bot']:
            # A repeated bot hunch is conversation, not independent evidence.
            if stance > 0 and brain.get('claim_basis', {}).get((speaker, target)) == 'hunch':
                continue
            bot_claims.setdefault(target, []).append(stance * 0.3 * trust)
        else:
            totals[target] += stance * trust
    for target, claims in bot_claims.items():
        # A chorus of identical unverified assertions is no stronger than its
        # strongest member. Direct human arguments and private checks still matter.
        totals[target] += max([0.0] + claims) + min([0.0] + claims)
    # Public human ballots are a small signal, not knowledge of a role.
    for speaker, target in context['votes'].items():
        if speaker in players and not players[speaker]['bot'] and target in totals:
            totals[target] += 0.5
    for target, prior in context.get('relationships', {}).items():
        if target in totals:
            totals[target] += prior
    for target in brain.get('disclosed', set()):
        if target in totals:
            totals[target] -= 0.4  # Acknowledged honesty, never proof of innocence.
    return totals


def choose_target(brain, context):
    totals = scores(brain, context)
    candidates = [p['id'] for p in context['players'] if p['alive'] and p['id'] != context['self']
                  and p['id'] not in context['allies'] and p['id'] not in context.get('protected', set()) and brain['checks'].get(p['id']) is not False]
    if not candidates:
        return 'skip'
    known = [pid for pid in candidates if brain['checks'].get(pid) is True]
    if known:
        return sorted(known)[0]
    top = max(totals.get(pid, 0) for pid in candidates)
    if top < -1:
        return 'skip'
    tied = [pid for pid in candidates if totals.get(pid, 0) == top]
    if brain['focus'] in tied:
        return brain['focus']
    # If an earlier focus died, keep bots from all choosing the first UUID.
    return min(tied, key=lambda pid: hashlib.sha256(
        (context['self'] + ':' + pid).encode()).digest())


def reply(brain, context, pending=None):
    players = {p['id']: p for p in context['players']}
    target = choose_target(brain, context)

    def name(pid):
        return '@' + players[pid]['name']

    def say(*options):
        # Adjacent bots have distinct phrasing without inventing evidence.
        return options[list(players).index(context['self']) % len(options)]
    if target == 'skip':
        return "I don't have a strong enough case against anyone. I lean towards skipping this vote. What evidence am I missing?"
    suspect = name(target)
    if pending:
        message, intent = pending['message'], pending['intent']
        speaker = name(message['speaker'])
        if intent['stances'].get(context['self'], 0) > 0:
            return say(
                f"{speaker}, I disagree about me. Look at my votes, not just a hunch. I lean towards {suspect}; what is your evidence?",
                f"{speaker}, I disagree about me. An accusation isn't proof. I lean towards {suspect}; can we compare our cases?",
                f"{speaker}, I disagree about me. Which choice of mine worries you? I lean towards {suspect}, but I'll answer your questions.")
        if intent['question']:
            supporters = [author for (author, accused), stance in brain['claims'].items()
                          if accused == target and stance > 0 and author in players
                          and brain.get('claim_basis', {}).get((author, accused)) != 'hunch']
            public_ballots = any(vote == target and not players[voter]['bot']
                                 for voter, vote in context['votes'].items() if voter in players)
            reason = ("the concerns raised in this chat" if supporters else
                      "the public voting so far" if public_ballots else "my own read so far, not proof")
            return f"{speaker}, I lean towards {suspect} because of {reason}. Let's hear their defense before voting."
        if intent['stances'].get(target, 0) > 0:
            return say(
                f"{speaker}, that makes me more suspicious too. I lean towards {suspect}. Can they explain their choices?",
                f"{speaker}, you've given me a reason to reconsider. I lean towards {suspect}. I'd like to hear their defense.",
                f"{speaker}, I can see that case. I lean towards {suspect} too, though agreement isn't proof.")
        defended = next((pid for pid, stance in intent['stances'].items() if stance < 0 and pid in players), None)
        if defended:
            return f"{speaker}, I'll weigh your defense of {name(defended)}. For now I lean towards {suspect}, but I'm listening."
        return f"{speaker}, I'm not convinced by that accusation. I lean towards {suspect}; let's compare reasons rather than pile on."
    return say(
        f"I lean towards {suspect}, but that's only a hunch. What do the rest of you think?",
        f"Before we rush to vote, I lean towards {suspect}. Does anyone have a reason to trust them?",
        f"I lean towards {suspect} for now. Let's compare our suspicions before we decide.")
