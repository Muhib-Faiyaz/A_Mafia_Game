"""Public complexity measurements and evidence-aware incident narration.

Canon stays in the case JSON. These helpers never use hidden roles, the solution,
or private witness knowledge to compose an incident or its optional quiet lead.
"""
from string import Formatter


LABELS = ('Very easy', 'Easy', 'Moderate', 'Difficult', 'Very difficult')
FACTOR_KEYS = ('clue_chain_length', 'cross_source_joins', 'timing_checks',
               'false_leads', 'interpretation_checks')


def _checks(case, category):
    """Only count authored reasoning checks anchored to real, distinct clues."""
    clue_ids = {clue.get('id') for clue in case.get('clues', [])}
    checks = case.get('reasoning', {}).get(category, [])
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, dict)
            and isinstance(check.get('note'), str) and check['note'].strip()
            and isinstance(check.get('requires'), list)
            and len(set(check['requires'])) >= 2
            and set(check['requires']) <= clue_ids][:2]


def complexity(case):
    """Return a fresh, spoiler-free rating, computed from the evidence ledger.

    Stored metadata is checked by ``validate_case``. Recompute for public output
    so stale ratings or additional private fields cannot leak into API payloads.
    A chain is a comparison's supporting evidence set, not a count of prose lines.
    """
    clues = {clue['id']: clue for clue in case.get('clues', [])}
    positive = [link for link in case.get('connections', []) if link.get('effect', 0) > 0]
    chain = max((len(set(link['requires'])) for link in positive), default=0)
    joins = max((max(0, len({clues[key].get('source') or 'scene'
                           for key in link['requires'] if key in clues}) - 1)
                 for link in positive), default=0)
    factors = dict(clue_chain_length=chain, cross_source_joins=joins,
                   timing_checks=len(_checks(case, 'timing')),
                   false_leads=sum(link.get('effect', 0) < 0 for link in case.get('connections', [])),
                   interpretation_checks=len(_checks(case, 'interpretation')))
    score = (max(0, chain - 2) + max(0, joins - 1) + factors['timing_checks']
             + min(2, factors['false_leads']) + factors['interpretation_checks'])
    stars = 1 if score <= 2 else 2 if score <= 4 else 3 if score <= 6 else 4 if score <= 8 else 5
    if stars == 1:
        reason = 'A short, direct chain joins witness testimony to a scene record.'
    else:
        timing = ('check the event order' if factors['timing_checks'] == 1 else
                  'compare separate time or disclosure sequences' if factors['timing_checks'] == 2 else
                  'check the supporting accounts')
        reason = f'Join up to {chain} evidence items across {joins + 1} sources and {timing}.'
        if factors['interpretation_checks']:
            reason += ' Distinguish what a record shows from what it only suggests.'
        if factors['false_leads']:
            reason += ' An admitted wrongdoing also needs to be separated from the main accusation.'
    return dict(stars=stars, label=LABELS[stars - 1], reason=reason, factors=factors)


def _template_valid(text):
    if not isinstance(text, str) or not text.strip():
        return False
    try:
        return all(field in (None, 'name') and not spec and not conversion
                   for _, field, spec, conversion in Formatter().parse(text))
    except ValueError:
        return False


def _incident(room, name, cause):
    case = room.get('scenario') or {}
    incidents = case.get('incidents', {})
    fallbacks = {
        'night': '{name} does not return from the watch. Their signed account remains in the file; what was never recorded can no longer be asked.',
        'vote': '{name} is placed under guard and leaves the inquiry. Their signed account remains in the file.',
        'rescue': '{name} survives the watch. The protector remains unnamed, and the inquiry can continue.',
    }
    template = incidents.get(cause, fallbacks[cause])
    if not _template_valid(template):
        template = fallbacks[cause]
    text = template.replace('{name}', str(name))
    public_ids = set(room.get('story', {}).get('revealed', {}))
    case_ids = {clue['id'] for clue in case.get('clues', [])}
    # A discovered fact can return as a hint only after all its sources are public.
    # This is narrator text; it is never an NPC assertion or a new journal clue.
    for lead in incidents.get('leads', []):
        required = lead.get('requires', [])
        if (lead.get('cause', 'night') == cause and required
                and set(required) <= case_ids and set(required) <= public_ids
                and room.get('day', 0) >= lead.get('min_day', 1)
                and _template_valid(lead.get('text'))):
            text += ' ' + lead['text'].replace('{name}', str(name))
            break
    return text


def death_story(room, name, cause):
    return _incident(room, name, 'vote' if cause == 'vote' else 'night')


def rescue_story(room, name):
    return _incident(room, name, 'rescue')


def validate_case(case):
    """Return actionable authoring errors, including stale complexity metadata.

    This is an offline canon check, not a mechanism for publishing hidden fields.
    Semantic reasoning notes still require human review against the prose.
    """
    errors = []
    cast = case.get('cast', [])
    keys = {actor.get('key') for actor in cast}
    names = {actor.get('name') for actor in cast}
    if len(cast) != 6 or len(keys) != 6 or len(names) != 6:
        errors.append('A case must have six distinct named witnesses.')
    if case.get('culprit') not in keys or case.get('doctor') not in keys or case.get('culprit') == case.get('doctor'):
        errors.append('The fixed culprit and Doctor must be different cast members.')
    clues = {clue.get('id'): clue for clue in case.get('clues', [])}
    if len(clues) != len(case.get('clues', [])):
        errors.append('Clue IDs must be unique.')
    for clue in clues.values():
        if clue.get('source') is not None and clue['source'] not in keys:
            errors.append(f"Unknown clue source: {clue.get('id')}.")
        if not isinstance(clue.get('day'), int) or clue['day'] < 1:
            errors.append(f"Invalid reveal round: {clue.get('id')}.")
    for actor in cast:
        for field in ('account', 'observation', 'secret', 'correction', 'defense', 'description', 'relationship'):
            if not actor.get(field):
                errors.append(f"Missing {field} for {actor.get('key')}.")
        for kind, field in (('account', 'account'), ('observation', 'observation'), ('admission', 'secret')):
            clue = clues.get(actor.get('key', '') + '-' + kind, {})
            if clue.get('text') != actor.get(field) or clue.get('source') != actor.get('key') or clue.get('kind') != kind:
                errors.append(f"Clue/profile mismatch: {actor.get('key')}-{kind}.")
    links = case.get('connections', [])
    if len({link.get('id') for link in links}) != len(links):
        errors.append('Comparison IDs must be unique.')
    for link in links:
        if link.get('speaker') not in keys or link.get('subject') not in keys:
            errors.append(f"Unknown comparison actor: {link.get('id')}.")
        required = link.get('requires', [])
        if len(set(required)) < 2 or not set(required) <= clues.keys():
            errors.append(f"Invalid comparison sources: {link.get('id')}.")
    for category in ('timing', 'interpretation'):
        checks = case.get('reasoning', {}).get(category)
        if not isinstance(checks, list) or len(checks) > 2 or len(_checks(case, category)) != len(checks):
            errors.append(f'Use zero to two evidenced {category} checks.')
    if case.get('complexity') != complexity(case):
        errors.append('Stored complexity must match the measured evidence demands.')
    incidents = case.get('incidents', {})
    for cause in ('night', 'vote', 'rescue'):
        if not _template_valid(incidents.get(cause)) or '{name}' not in incidents.get(cause, ''):
            errors.append(f'Missing or invalid {cause} incident template.')
    for lead in incidents.get('leads', []):
        required = lead.get('requires', [])
        if (not required or not set(required) <= clues.keys() or not _template_valid(lead.get('text'))
                or lead.get('cause', 'night') not in ('night', 'vote', 'rescue')
                or not isinstance(lead.get('min_day', 1), int) or lead.get('min_day', 1) < 1):
            errors.append('Incident leads need valid sources, a cause, text, and a reveal round.')
    if len(case.get('opening', [])) != 3 or len(case.get('timeline', [])) < 5 or not case.get('reconstruction'):
        errors.append('Keep the opening, fixed chronology, and final reconstruction complete.')
    return errors
