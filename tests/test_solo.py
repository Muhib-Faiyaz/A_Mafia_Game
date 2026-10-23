import copy
import json
import time
import unittest
from unittest.mock import patch
import app as game
import bot_brain
import solo_story


class SoloTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.client = game.app.test_client()

    def post(self, route, body, status=200):
        response = self.client.post('/api/' + route, json=body)
        self.assertEqual(response.status_code, status, (response.get_json() or {}).get('error', route))
        return response.get_json()

    def create(self, case=None, name='Reader'):
        with patch.object(solo_story, 'choose', return_value=copy.deepcopy(case or solo_story.SCENARIOS[0])):
            return self.post('solo', dict(name=name, include_state=True))

    def test_new_solo_controls_reject_npc_sessions_and_cannot_stack_team_claims(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        npc = next(pid for pid, player in room['players'].items() if player['bot'])
        routes = {
            'solo-question': dict(target=npc, question='detail'),
            'solo-influence': dict(target=npc, stance='suspect'),
            'solo-evidence': dict(action='inspect'),
            'solo-proceed': {},
        }
        for route, body in routes.items():
            self.post(route, dict(code=identity['code'], pid=npc, **body), 403)
        self.assertEqual(room['story']['claims'], {})
        self.assertEqual(room['story']['revisions'], [])

    def detective_turn(self, identity):
        self.post('solo-proceed', identity)
        self.post('solo-proceed', identity)
        state = self.post('state', identity)
        self.assertEqual(state['night_step'], 'detective')
        return state

    def day(self, case=None):
        identity = self.create(case)
        self.post('start', identity)
        self.detective_turn(identity)
        room = game.rooms[identity['code']]
        # Story fixtures keep the whole cast available; mortality has separate coverage.
        room['night']['victim'] = None
        self.post('solo-proceed', identity)
        self.assertEqual(room['phase'], 'day')
        return identity, room

    def next_round(self, identity):
        room = game.rooms[identity['code']]
        self.post('proceed', identity)
        self.post('vote', dict(identity, target='skip'))
        self.assertEqual(room['phase'], 'night')
        self.detective_turn(identity)
        room['night']['victim'] = None
        self.post('solo-proceed', identity)
        self.assertEqual(room['phase'], 'day')

    def publisher(self, room):
        return lambda name, text, kind='msg': game.chat_add(room, 'town', name, text, kind)

    def available_question(self, state, question='detail', exclude=None):
        for actor in state['scenario']['cast']:
            if actor['alive'] and actor['id'] != exclude:
                for option in actor['question_options']:
                    if option['id'] == question and option['available']:
                        return actor, option
        self.fail('No available ' + question + ' question')

    def test_seven_cases_have_valid_canon_question_content_and_recorded_origins(self):
        self.assertEqual(len(solo_story.SCENARIOS), 7)
        self.assertEqual(len({s['id'] for s in solo_story.SCENARIOS}), 7)
        self.assertEqual(len({tuple(s['opening']) for s in solo_story.SCENARIOS}), 7)
        self.assertEqual(sum(len(s['origin']['combined_from']) == 2 for s in solo_story.SCENARIOS), 1)
        self.assertTrue(any('story-skills' in json.dumps(s['origin']) for s in solo_story.SCENARIOS))
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                self.assertTrue(case['origin']['label'])
                self.assertTrue(case['origin']['skills'])
                self.assertEqual(len(case['opening']), 3)
                self.assertEqual(len(case['cast']), 6)
                keys = {p['key'] for p in case['cast']}
                self.assertEqual(len(keys), 6)
                self.assertIn(case['culprit'], keys)
                self.assertIn(case['doctor'], keys)
                self.assertNotEqual(case['culprit'], case['doctor'])
                clues = {c['id']: c for c in case['clues']}
                self.assertEqual(len(clues), len(case['clues']))
                for actor in case['cast']:
                    for field in ['account', 'observation', 'secret', 'correction', 'description', 'relationship']:
                        self.assertTrue(actor[field], field)
                    for kind in ['account', 'observation', 'admission']:
                        self.assertIn(actor['key'] + '-' + kind, clues)
                        field = 'secret' if kind == 'admission' else kind
                        self.assertEqual(clues[actor['key'] + '-' + kind]['text'], actor[field])
                for link in case['connections']:
                    self.assertIn(link['speaker'], keys)
                    self.assertIn(link['subject'], keys)
                    self.assertGreaterEqual(len(link['requires']), 2)
                    self.assertTrue(set(link['requires']) <= clues.keys())
                against = [link for link in case['connections'] if link['subject'] == case['culprit'] and link['effect'] > 0]
                self.assertGreaterEqual(len(against), 2)
                self.assertTrue(any(link['effect'] < 0 for link in case['connections']))
                self.assertGreaterEqual(len(case['timeline']), 5)
                self.assertTrue(case['reconstruction'])
                culprit = next(p for p in case['cast'] if p['key'] == case['culprit'])
                self.assertIn(culprit['name'], ' '.join(case['reconstruction']))

    def test_story_catalog_exposes_selection_and_origins_without_the_solution(self):
        response = self.client.get('/api/stories')
        self.assertEqual(response.status_code, 200)
        catalog = response.get_json()['stories']
        self.assertEqual({s['id'] for s in catalog}, {s['id'] for s in solo_story.SCENARIOS})
        for entry in catalog:
            self.assertTrue(entry['title'])
            self.assertTrue(entry['setting'])
            self.assertTrue(entry['origin']['label'])
            for private in ['culprit', 'doctor', 'clues', 'connections', 'timeline', 'solution', 'reconstruction']:
                self.assertNotIn(private, entry)

    def test_player_can_choose_any_case_or_request_random_without_mutating_canon(self):
        for case in solo_story.SCENARIOS:
            selected = self.post('solo', dict(name='Reader', scenario_id=case['id'], previous_scenario=case['id'], include_state=True))
            self.assertEqual(selected['state']['scenario']['id'], case['id'])
        before = set(game.rooms)
        self.post('solo', dict(name='Reader', scenario_id='missing-case'), 400)
        self.assertEqual(set(game.rooms), before)
        previous = solo_story.SCENARIOS[0]['id']
        selected = self.post('solo', dict(name='Reader', scenario_id='random', previous_scenario=previous, include_state=True))
        self.assertNotEqual(selected['state']['scenario']['id'], previous)
        room = game.rooms[selected['code']]
        room['scenario']['cast'][0]['name'] = 'Changed'
        self.assertFalse(any(c['cast'][0]['name'] == 'Changed' for c in solo_story.SCENARIOS))

    def test_every_case_is_paused_private_and_has_one_fixed_mafia(self):
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                identity = self.create(case)
                room = game.rooms[identity['code']]
                state = identity['state']
                self.assertEqual(state['phase'], 'lobby')
                self.assertEqual(state['settings']['mafia_count'], 1)
                self.assertEqual(len(state['players']), 7)
                serialized = json.dumps(state, ensure_ascii=False)
                for clue in case['clues']:
                    self.assertNotIn(clue['text'], serialized)
                self.assertNotIn(case['solution'], serialized)
                self.assertNotIn('culprit', state['scenario'])
                self.post('start', identity)
                roles = [p['role'] for p in room['players'].values()]
                self.assertEqual(roles.count('mafia'), 1)
                self.assertEqual(roles.count('doctor'), 1)
                self.assertEqual(roles.count('town'), 4)
                self.assertEqual(room['players'][solo_story.cast_ids(room)[case['culprit']]]['role'], 'mafia')
                self.assertEqual(room['night_step'], 'mafia')

    def test_solo_turns_have_no_deadlines_and_advance_only_when_proceeded(self):
        identity = self.create()
        self.post('start', identity)
        for step in ['mafia', 'doctor', 'detective']:
            before = self.post('state', identity)
            self.assertEqual(before['night_step'], step)
            self.assertEqual((before['timer_left'], before['timer_total']), (0, 0))
            with patch.object(game.time, 'time', return_value=time.time() + 24 * 3600):
                for _ in range(3):
                    after = self.post('state', identity)
                    self.assertEqual(after['night_step'], step)
            self.post('solo-proceed', identity)
        day = self.post('state', identity)
        self.assertEqual(day['phase'], 'day')
        self.assertFalse(day['voting'])
        self.assertEqual((day['timer_left'], day['timer_total']), (0, 0))
        with patch.object(game.time, 'time', return_value=time.time() + 24 * 3600):
            self.assertFalse(self.post('state', identity)['voting'])
        self.post('proceed', identity)
        self.assertTrue(self.post('state', identity)['voting'])

    def test_investigation_records_immediately_but_waits_for_explicit_proceed(self):
        identity = self.create()
        self.post('start', identity)
        self.detective_turn(identity)
        room = game.rooms[identity['code']]
        target = game.alive(room, 'mafia')[0]
        self.post('act', dict(identity, target=target))
        state = self.post('state', identity)
        self.assertTrue(state['investigation']['correct'])
        self.assertEqual(state['phase'], 'night')
        self.assertEqual(state['night_step'], 'detective')
        self.post('act', dict(identity, target=target), 400)
        self.post('solo-proceed', identity)
        self.assertEqual(self.post('state', identity)['phase'], 'day')

    def test_accounts_appear_once_per_witness_per_round_without_online_templates(self):
        identity, room = self.day()
        with patch.object(bot_brain, 'reply', side_effect=AssertionError('Online reply used in solo')):
            for _ in range(15):
                self.post('state', identity)
        living_witnesses = {pid for pid, p in room['players'].items() if p['bot'] and p['alive']}
        self.assertEqual(set(room['story']['account_rounds'][1]), living_witnesses)
        for actor in room['scenario']['cast']:
            messages = [c for c in room['chat'] if c['n'] == actor['name'] and c['day'] == 1 and actor['account'] in c['t']]
            self.assertEqual(len(messages), 1, actor['name'])
        first_round_count = len(room['chat'])
        for _ in range(8):
            self.post('state', identity)
        self.assertEqual(len(room['chat']), first_round_count)
        self.next_round(identity)
        self.assertEqual(set(room['story']['account_rounds'][2]), living_witnesses)
        second_round_count = len(room['chat'])
        for _ in range(8):
            self.post('state', identity)
        self.assertEqual(len(room['chat']), second_round_count)
        self.assertFalse(any('I lean towards' in c['t'] for c in room['chat']))

    def test_one_selected_question_changes_testimony_and_blocks_all_other_questions_that_round(self):
        identity, room = self.day()
        before = self.post('state', identity)
        actor, option = self.available_question(before)
        profile = room['players'][actor['id']]['character']
        self.post('solo-question', dict(identity, target=actor['id'], question=option['id']))
        after = self.post('state', identity)
        quota = after['scenario']['interrogation']
        self.assertTrue(quota['used'])
        self.assertEqual(quota['target_name'], actor['name'])
        self.assertEqual(quota['question_id'], option['id'])
        changed = next(p for p in after['scenario']['cast'] if p['id'] == actor['id'])
        self.assertNotEqual(changed['statement'], actor['statement'])
        self.assertFalse(any(q['available'] for p in after['scenario']['cast'] for q in p['question_options']))
        self.assertIn(profile['observation'], json.dumps(after['scenario'], ensure_ascii=False))
        other = next(p for p in after['scenario']['cast'] if p['alive'] and p['id'] != actor['id'])
        self.post('solo-question', dict(identity, target=other['id'], question='motive'), 400)
        self.post('solo-question', dict(identity, target=actor['id'], question='correction'), 400)
        for _ in range(5):
            self.post('state', identity)
        speeches = [c for c in room['chat'] if c['n'] == actor['name'] and c['t'] == profile['observation']]
        self.assertLessEqual(len(speeches), 1)
        self.next_round(identity)
        state = self.post('state', identity)
        self.assertFalse(state['scenario']['interrogation']['used'])
        options = next(p for p in state['scenario']['cast'] if p['id'] == actor['id'])['question_options']
        self.assertFalse(next(q for q in options if q['id'] == 'detail')['available'])
        self.post('solo-question', dict(identity, target=other['id'], question='motive'))
        self.assertTrue(self.post('state', identity)['scenario']['interrogation']['used'])

    def test_each_of_the_three_questions_publishes_the_matching_authored_change(self):
        for question, field in [('detail', 'observation'), ('motive', 'secret'), ('correction', 'correction')]:
            with self.subTest(question=question):
                identity, room = self.day()
                state = self.post('state', identity)
                actor, _ = self.available_question(state, question)
                self.post('solo-question', dict(identity, target=actor['id'], question=question))
                public = self.post('state', identity)['scenario']
                changed = next(p for p in public['cast'] if p['id'] == actor['id'])
                self.assertNotEqual(changed['statement'], actor['statement'])
                self.assertIn(room['players'][actor['id']]['character'][field], json.dumps(public, ensure_ascii=False))

    def test_question_validation_does_not_consume_the_only_question(self):
        identity, room = self.day()
        state = self.post('state', identity)
        actor, _ = self.available_question(state)
        for target, question in [('missing', 'detail'), (identity['pid'], 'detail'), (actor['id'], 'free-text')]:
            self.post('solo-question', dict(identity, target=target, question=question), 400)
            self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])
        dead = next(pid for pid, p in room['players'].items() if p['bot'] and pid != actor['id'])
        game.record_death(room, dead, 'night')
        self.post('solo-question', dict(identity, target=dead, question='detail'), 400)
        self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])

    def test_questions_close_during_voting_and_night(self):
        identity, room = self.day()
        actor, _ = self.available_question(self.post('state', identity))
        self.post('proceed', identity)
        self.post('solo-question', dict(identity, target=actor['id'], question='motive'), 400)
        self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])
        self.post('vote', dict(identity, target='skip'))
        self.post('solo-question', dict(identity, target=actor['id'], question='motive'), 400)
        self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])

    def test_no_typed_public_questions_or_accusations_and_private_team_chat_stays_available(self):
        identity, _ = self.day()
        for text in ['What happened?', 'I suspect someone', '/vote someone']:
            self.post('chat', dict(identity, text=text), 400)
        self.post('team-chat', dict(identity, text='Let us compare these statements.'))
        state = self.post('state', identity)
        self.assertTrue(any(c['t'] == 'Let us compare these statements.' for c in state['team_chat']))
        self.assertFalse(any(c['t'] == 'Let us compare these statements.' for c in state['chat']))

    def test_inspection_and_comparison_do_not_consume_question_and_hide_unpublished_content(self):
        identity, room = self.day()
        state = self.post('state', identity)
        docs = [c for c in room['scenario']['clues'] if c['kind'] == 'document']
        self.assertNotIn(docs[0]['text'], json.dumps(state, ensure_ascii=False))
        self.post('solo-evidence', dict(identity, action='inspect'))
        state = self.post('state', identity)
        self.assertTrue(any(e['kind'] == 'document' for e in state['scenario']['journal']))
        self.post('solo-evidence', dict(identity, action='compare'))
        self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])
        self.post('solo-evidence', dict(identity, action='invent'), 400)
        self.assertNotIn(room['scenario']['solution'], json.dumps(state, ensure_ascii=False))

    def test_scene_inspection_recovers_missing_witness_observations_without_question_or_ghost_dialogue(self):
        identity, room = self.day()
        ids = solo_story.cast_ids(room)
        unseen = next(c for c in room['scenario']['clues'] if c['kind'] == 'observation' and c['id'] not in room['story']['revealed'])
        target = ids[unseen['source']]
        name = room['players'][target]['name']
        game.record_death(room, target, 'night')
        before = len([m for m in room['chat'] if m['n'] == name])
        for _ in range(len(room['scenario']['clues'])):
            self.post('solo-evidence', dict(identity, action='inspect'))
            if unseen['id'] in room['story']['revealed']:
                break
        self.assertTrue(room['story']['revealed'][unseen['id']]['archived'])
        self.assertEqual(len([m for m in room['chat'] if m['n'] == name]), before)
        self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])
        self.assertNotIn(unseen['source'] + '-admission', room['story']['revealed'])

    def test_all_cases_are_winnable_with_one_question_per_round_and_public_evidence(self):
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                identity = self.create(case)
                room = game.rooms[identity['code']]
                ids = solo_story.cast_ids(room)
                culprit = ids[case['culprit']]
                clues = {c['id']: c for c in case['clues']}
                self.post('start', identity)
                positive = [link for link in case['connections'] if link['subject'] == case['culprit'] and link['effect'] > 0]
                for _ in range(6):
                    self.detective_turn(identity)
                    self.post('act', dict(identity, target=culprit))
                    self.post('solo-proceed', identity)
                    if room['phase'] == 'over':
                        break
                    # All public exhibits and recorded notes may be inspected, but living
                    # people may receive only the one selected question each round.
                    for _ in range(len(case['clues'])):
                        before = len(room['story']['revealed'])
                        self.post('solo-evidence', dict(identity, action='inspect'))
                        if len(room['story']['revealed']) == before:
                            break
                    revealed = set(room['story']['revealed'])
                    supported = any(link['id'] in room['story']['connections'] for link in positive)
                    if not supported:
                        state = self.post('state', identity)
                        candidates = []
                        for link in positive:
                            missing = [clues[key] for key in link['requires'] if key not in revealed]
                            if any(c['source'] and not room['players'][ids[c['source']]]['alive'] for c in missing):
                                continue
                            for clue in missing:
                                question = {'observation': 'detail', 'admission': 'motive', 'correction': 'correction'}.get(clue['kind'])
                                if question:
                                    actor = next(p for p in state['scenario']['cast'] if p['id'] == ids[clue['source']])
                                    if any(q['id'] == question and q['available'] for q in actor['question_options']):
                                        candidates.append((len(missing), actor['id'], question))
                        self.assertTrue(candidates, 'No legal remaining path to a corroborated case')
                        _, target, question = min(candidates)
                        self.post('solo-question', dict(identity, target=target, question=question))
                    supported = any(link['id'] in room['story']['connections'] for link in positive)
                    if supported:
                        self.post('solo-influence', dict(identity, target=culprit, stance='suspect'))
                    self.post('proceed', identity)
                    self.post('vote', dict(identity, target=culprit if supported else 'skip'))
                    if room['phase'] == 'over':
                        break
                self.assertEqual(room.get('winner'), 'town', case['id'])
                self.assertEqual(self.post('state', identity)['scenario']['solution'], case['solution'])

    def test_structured_influence_changes_votes_without_stacking_or_consuming_question(self):
        identity, room = self.day()
        ids = solo_story.cast_ids(room)
        link = next(c for c in room['scenario']['connections'] if c['effect'] > 0)
        clues = {c['id']: c for c in room['scenario']['clues']}
        for key in link['requires']:
            solo_story.reveal(room, clues[key], self.publisher(room))
        solo_story.connect(room, self.publisher(room))
        target = ids[link['subject']]
        voter = next(pid for pid, p in room['players'].items() if p['bot'] and pid != target)
        self.post('solo-influence', dict(identity, target=target, stance='suspect'))
        self.assertEqual(solo_story.vote_target(room, voter), target)
        score = solo_story.suspicion(room, voter)[target]
        self.post('solo-influence', dict(identity, target=target, stance='suspect'))
        self.assertEqual(solo_story.suspicion(room, voter)[target], score)
        self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])
        self.post('solo-influence', dict(identity, target=target, stance='defend'))
        self.assertLess(solo_story.suspicion(room, voter)[target], score)
        self.post('solo-influence', dict(identity, target=target, stance='neutral'))
        self.post('solo-influence', dict(identity, target='missing', stance='suspect'), 400)
        self.post('solo-influence', dict(identity, target=target, stance='nonsense'), 400)

    def test_votes_do_not_read_hidden_roles_or_unpublished_solution(self):
        identity, room = self.day()
        ids = solo_story.cast_ids(room)
        voter = ids[room['scenario']['doctor']]
        before = solo_story.suspicion(room, voter)
        culprit = ids[room['scenario']['culprit']]
        innocent = next(pid for pid in ids.values() if pid not in (culprit, voter))
        room['players'][culprit]['role'], room['players'][innocent]['role'] = 'town', 'mafia'
        room['scenario']['solution'] = 'The author knows something else.'
        self.assertEqual(before, solo_story.suspicion(room, voter))

    def test_alias_collision_updates_all_private_and_public_case_references(self):
        case = solo_story.SCENARIOS[0]
        actor = case['cast'][0]
        identity = self.create(case, name=actor['name'])
        room = game.rooms[identity['code']]
        renamed = room['scenario']['cast'][0]
        self.assertEqual(renamed['name'], actor['name'] + ' Vale')
        self.assertEqual(renamed['key'], actor['key'])
        self.assertEqual(len({p['name'] for p in room['players'].values()}), 7)
        self.assertEqual(case['cast'][0]['name'], actor['name'])

    def test_context_has_only_the_current_characters_private_background(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        actors = [pid for pid, p in room['players'].items() if p['bot']]
        context = game.bot_context(room, actors[0])
        self.assertIn('secret', context['character'])
        for pid in actors[1:]:
            self.assertNotIn(room['players'][pid]['character']['secret'], repr(context))

    def test_completed_and_host_ended_cases_explain_who_did_what_and_why(self):
        for finished in [False, True]:
            with self.subTest(finished=finished):
                identity, room = self.day()
                if finished:
                    game.record_death(room, game.alive(room, 'mafia')[0], 'vote')
                    game.check_win(room)
                else:
                    self.post('end', identity)
                scenario = self.post('state', identity)['scenario']
                self.assertEqual(scenario['solution'], room['scenario']['solution'])
                self.assertEqual(scenario['timeline'], room['scenario']['timeline'])
                self.assertEqual(scenario['reconstruction'], room['scenario']['reconstruction'])
                self.assertTrue(scenario['reconstruction'])

    def test_replay_preserves_culprit_but_clears_the_case_and_question_quota(self):
        identity, room = self.day()
        actor, option = self.available_question(self.post('state', identity))
        self.post('solo-question', dict(identity, target=actor['id'], question=option['id']))
        self.post('end', identity)
        roles = {pid: p['role'] for pid, p in room['players'].items()}
        self.post('restart', identity)
        self.assertEqual(roles, {pid: p['role'] for pid, p in room['players'].items()})
        self.assertEqual(self.post('state', identity)['scenario']['journal'], [])
        self.assertFalse(self.post('state', identity)['scenario']['interrogation']['used'])
        self.assertEqual(room['night_step'], 'mafia')

    def test_solo_rooms_reject_public_joining_and_cast_or_rule_changes(self):
        identity = self.create()
        self.post('join', dict(code=identity['code'], name='Outsider'), 400)
        self.post('bot', dict(identity, count=1), 400)
        self.post('settings', dict(identity, mafia_count=2), 400)
        self.assertEqual(len(game.rooms[identity['code']]['players']), 7)

    def test_online_rooms_keep_their_normal_workflow(self):
        identity = self.post('create', dict(name='Host', include_state=True))
        self.assertEqual(identity['state']['mode'], 'online')
        self.assertIsNone(identity['state']['scenario'])
        self.post('join', dict(code=identity['code'], name='Friend'))
        self.post('bot', dict(identity, count=1))
        self.post('start', identity)
        self.assertEqual(len(game.rooms[identity['code']]['players']), 3)
