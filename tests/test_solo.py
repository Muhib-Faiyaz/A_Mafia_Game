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
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def create(self, case=None, name='Reader'):
        with patch.object(solo_story, 'choose', return_value=copy.deepcopy(case or solo_story.SCENARIOS[0])):
            return self.post('solo', dict(name=name, include_state=True))

    def day(self, case=None):
        identity = self.create(case)
        self.post('start', identity)
        room = game.rooms[identity['code']]
        room.update(phase='day', discuss_until=time.time() + 10000)
        return identity, room

    def tell(self, identity, text):
        game.rooms[identity['code']]['players'][identity['pid']]['last'] = 0
        return self.post('chat', dict(identity, text=text, include_state=True))

    def publisher(self, room):
        return lambda name, text, kind='msg': game.chat_add(room, 'town', name, text, kind)

    def test_seven_complete_cases_have_consistent_references_and_two_independent_clue_chains(self):
        self.assertEqual(len(solo_story.SCENARIOS), 7)
        self.assertEqual(len({s['id'] for s in solo_story.SCENARIOS}), 7)
        self.assertEqual(len({tuple(s['opening']) for s in solo_story.SCENARIOS}), 7)
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                self.assertEqual(len(case['opening']), 3)
                self.assertEqual(len(case['cast']), 6)
                keys = {p['key'] for p in case['cast']}
                self.assertEqual(len(keys), 6)
                self.assertIn(case['culprit'], keys)
                self.assertIn(case['doctor'], keys)
                self.assertNotEqual(case['culprit'], case['doctor'])
                clues = {c['id']: c for c in case['clues']}
                self.assertEqual(len(clues), len(case['clues']))
                prose = [c['text'] for c in case['clues']]
                self.assertEqual(len(prose), len(set(prose)))
                for p in case['cast']:
                    self.assertTrue(all(p[field] for field in ['account', 'observation', 'secret', 'description', 'relationship', 'defense']))
                    for kind in ['account', 'observation', 'admission']:
                        self.assertIn(p['key'] + '-' + kind, clues)
                        field = 'secret' if kind == 'admission' else kind
                        self.assertEqual(clues[p['key'] + '-' + kind]['text'], p[field])
                for link in case['connections']:
                    self.assertIn(link['speaker'], keys)
                    self.assertIn(link['subject'], keys)
                    self.assertGreaterEqual(len(link['requires']), 2)
                    self.assertTrue(set(link['requires']) <= clues.keys())
                against = [link for link in case['connections'] if link['subject'] == case['culprit'] and link['effect'] > 0]
                self.assertGreaterEqual(len(against), 2)
                self.assertNotEqual(set(against[0]['requires']), set(against[1]['requires']))
                self.assertTrue(any(link['effect'] < 0 for link in case['connections']))
                self.assertGreaterEqual(len(case['timeline']), 5)
                self.assertEqual(len(case['chapters']), 3)

    def test_every_case_starts_paused_private_and_uses_exactly_one_canonical_mafia(self):
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                identity = self.create(case)
                room = game.rooms[identity['code']]
                state = identity['state']
                self.assertEqual(state['mode'], 'solo')
                self.assertEqual(state['scenario']['id'], case['id'])
                self.assertEqual(state['phase'], 'lobby')
                self.assertEqual(state['timer_total'], 0)
                self.assertEqual(state['settings']['mafia_count'], 1)
                self.assertEqual(len(state['players']), 7)
                serialized = json.dumps(state, ensure_ascii=False)
                for clue in case['clues']:
                    self.assertNotIn(clue['text'], serialized)
                self.assertNotIn(case['solution'], serialized)
                self.assertNotIn('culprit', state['scenario'])
                with patch.object(game.time, 'time', return_value=time.time() + 600):
                    self.assertEqual(self.post('state', identity)['phase'], 'lobby')
                self.post('start', identity)
                roles = [p['role'] for p in room['players'].values()]
                self.assertEqual(roles.count('mafia'), 1)
                self.assertEqual(roles.count('doctor'), 1)
                self.assertEqual(roles.count('town'), 4)
                ids = solo_story.cast_ids(room)
                self.assertEqual(room['players'][ids[case['culprit']]]['role'], 'mafia')
                self.assertEqual(room['night_step'], 'detective')
                self.assertNotEqual(room['night']['victim'], identity['pid'])

    def test_solo_rooms_reject_public_joining_and_cast_or_rule_changes(self):
        identity = self.create()
        self.post('join', dict(code=identity['code'], name='Outsider'), 400)
        self.post('bot', dict(identity, count=1), 400)
        self.post('settings', dict(identity, mafia_count=2), 400)
        self.assertEqual(len(game.rooms[identity['code']]['players']), 7)

    def test_alias_collision_updates_accounts_clues_and_solution_consistently(self):
        identity = self.create(name='Mara')
        room = game.rooms[identity['code']]
        self.assertIn('Mara Vale', [p['name'] for p in identity['state']['scenario']['cast']])
        account = next(c for c in room['scenario']['clues'] if c['id'] == 'ivo-account')
        self.assertEqual(room['scenario']['cast'][0]['key'], 'mara')
        self.assertIn('Mara Vale', room['scenario']['connections'][2]['text'])
        self.assertNotIn('Mara Vale', solo_story.SCENARIOS[0]['connections'][2]['text'])
        self.assertEqual(len({p['name'] for p in room['players'].values()}), 7)

    def test_last_case_can_be_excluded_without_mutating_catalog(self):
        with patch.object(solo_story.random, 'choice', side_effect=lambda cases: cases[0]):
            selected = solo_story.choose(solo_story.SCENARIOS[0]['id'])
        self.assertNotEqual(selected['id'], solo_story.SCENARIOS[0]['id'])
        selected['cast'][0]['name'] = 'Changed'
        self.assertNotEqual(solo_story.SCENARIOS[1]['cast'][0]['name'], 'Changed')

    def test_trust_changes_disclosure_and_repeated_questions_do_not_repeat_prose(self):
        identity, room = self.day()
        actor = room['players'][solo_story.cast_ids(room)['mara']]
        self.tell(identity, '@Mara, what are you hiding?')
        self.assertNotIn('mara-admission', room['story']['revealed'])
        self.tell(identity, 'I trust Mara')
        self.tell(identity, '@Mara, what are you hiding?')
        self.assertEqual(room['story']['revealed']['mara-admission']['text'], actor['character']['secret'])
        before = len([c for c in room['chat'] if c['n'] == 'Mara'])
        for _ in range(5):
            response = self.tell(identity, '@Mara, what are you hiding?')
        self.assertEqual(before, len([c for c in room['chat'] if c['n'] == 'Mara']))
        self.assertIn('No new testimony', response['feedback'])

    def test_repeated_pressure_discloses_a_new_fact_once_without_trust(self):
        identity, room = self.day()
        self.tell(identity, '@Mara, what are you hiding?')
        self.tell(identity, '@Mara, please be honest about your secret')
        self.assertIn('mara-admission', room['story']['revealed'])
        self.assertEqual(sum(c['t'] == room['players'][solo_story.cast_ids(room)['mara']]['character']['secret'] for c in room['chat']), 1)

    def test_solo_uses_no_online_reply_and_does_not_repeat_at_each_dawn(self):
        identity, room = self.day()
        with patch.object(bot_brain, 'reply', side_effect=AssertionError('Online reply used in solo')):
            for day in range(1, 6):
                room['day'] = day
                for _ in range(12):
                    room['story']['last_spoke'] = 0
                    game.bot_discussion(room)
            self.tell(identity, '@Mara, what is your account?')
        speeches = [c['t'] for c in room['chat'] if c['k'] == 'msg' and c['n'] != 'Reader']
        self.assertEqual(len(speeches), len(set(speeches)))
        self.assertFalse(any('I lean towards' in text for text in speeches))
        self.assertEqual(len(room['story']['chapters']), 3)

    def test_missing_witnesses_only_contribute_pre_watch_notes_not_new_dialogue_or_secrets(self):
        identity, room = self.day()
        pid = solo_story.cast_ids(room)['mara']
        game.record_death(room, pid, 'night')
        self.tell(identity, '@Mara, what is your account?')
        self.tell(identity, '@Mara, what did you notice?')
        self.tell(identity, '@Mara, what are you hiding?')
        self.assertTrue(room['story']['revealed']['mara-account']['archived'])
        self.assertNotIn('mara-admission', room['story']['revealed'])
        self.assertFalse(any(c['n'] == 'Mara' for c in room['chat']))
        self.assertTrue(any('sealed pre-watch notes' in c['t'] for c in room['chat']))

    def test_evidence_is_not_public_until_revealed_and_connections_require_all_sources(self):
        identity, room = self.day()
        link = room['scenario']['connections'][0]
        clues = {c['id']: c for c in room['scenario']['clues']}
        for key in link['requires'][:-1]:
            solo_story.reveal(room, clues[key], self.publisher(room))
        self.assertFalse(solo_story.connect(room, self.publisher(room)))
        self.assertNotIn(link['text'], json.dumps(game.view(room, identity['pid']), ensure_ascii=False))
        solo_story.reveal(room, clues[link['requires'][-1]], self.publisher(room))
        self.assertTrue(solo_story.connect(room, self.publisher(room)))
        state = game.view(room, identity['pid'])
        self.assertEqual(state['scenario']['connections'][0]['sources'], link['requires'])
        self.assertNotIn('effect', state['scenario']['connections'][0])
        self.assertNotIn(room['scenario']['solution'], json.dumps(state, ensure_ascii=False))

    def test_each_case_can_be_solved_by_combining_testimony_and_exhibits(self):
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                identity, room = self.day(case)
                ids = solo_story.cast_ids(room)
                culprit = ids[case['culprit']]
                voter = next(pid for key, pid in ids.items() if key != case['culprit'])
                self.assertEqual(solo_story.vote_target(room, voter), 'skip')
                for clue in case['clues']:
                    solo_story.reveal(room, clue, self.publisher(room))
                while solo_story.connect(room, self.publisher(room)):
                    pass
                self.assertEqual(solo_story.vote_target(room, voter), culprit)
                self.assertEqual(len(room['story']['connections']), 3)
                self.assertTrue(any(c['n'] == room['players'][culprit]['name'] and c['t'] == case['connections'][0]['reply'] for c in room['chat']))

    def test_all_seven_cases_complete_through_public_interviews_and_actual_ballots(self):
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                identity = self.create(case)
                room = game.rooms[identity['code']]
                self.post('start', identity)
                ids = solo_story.cast_ids(room)
                self.post('act', dict(identity, target=ids[case['doctor']]))
                self.assertEqual(room['phase'], 'day')
                for character in case['cast']:
                    name = character['name']
                    self.tell(identity, f'@{name}, what is your account?')
                    self.tell(identity, f'@{name}, what did you notice?')
                    if room['players'][ids[character['key']]]['alive']:
                        self.tell(identity, f'I trust {name}')
                        self.tell(identity, f'@{name}, what are you hiding?')
                for _ in range(2):
                    self.tell(identity, 'Inspect the scene for evidence.')
                culprit = ids[case['culprit']]
                self.tell(identity, 'I suspect ' + room['players'][culprit]['name'])
                self.assertTrue(room['story']['connections'])
                self.post('proceed', identity)
                self.assertEqual(room['phase'], 'day')
                self.post('vote', dict(identity, target=culprit))
                self.assertEqual(room['winner'], 'town')
                self.assertEqual(room['players'][identity['pid']]['round_points'], 1)
                self.assertEqual(self.post('state', identity)['scenario']['solution'], case['solution'])

    def test_player_arguments_change_votes_but_repeated_claims_do_not_multiply(self):
        identity, room = self.day()
        ids = solo_story.cast_ids(room)
        link = room['scenario']['connections'][0]
        clues = {c['id']: c for c in room['scenario']['clues']}
        for key in link['requires']:
            solo_story.reveal(room, clues[key], self.publisher(room))
        solo_story.connect(room, self.publisher(room))
        voter = ids['ada']
        self.assertEqual(solo_story.vote_target(room, voter), 'skip')
        self.tell(identity, 'I suspect Elias')
        self.assertEqual(solo_story.vote_target(room, voter), ids['elias'])
        score = solo_story.suspicion(room, voter)[ids['elias']]
        self.tell(identity, 'I suspect Elias')
        self.assertEqual(solo_story.suspicion(room, voter)[ids['elias']], score)
        self.tell(identity, 'I trust Elias')
        self.assertEqual(solo_story.vote_target(room, voter), 'skip')

    def test_votes_do_not_read_hidden_roles_or_unpublished_solution(self):
        identity, room = self.day()
        ids = solo_story.cast_ids(room)
        voter = ids['ada']
        before = solo_story.suspicion(room, voter)
        room['players'][ids['elias']]['role'], room['players'][ids['mara']]['role'] = 'town', 'mafia'
        room['scenario']['solution'] = 'The author knows something else.'
        self.assertEqual(before, solo_story.suspicion(room, voter))
        self.assertEqual(solo_story.vote_target(room, voter), 'skip')

    def test_public_revelations_change_the_killers_next_target(self):
        identity, room = self.day()
        ids = solo_story.cast_ids(room)
        link = room['scenario']['connections'][0]
        clues = {c['id']: c for c in room['scenario']['clues']}
        for key in link['requires']:
            solo_story.reveal(room, clues[key], self.publisher(room))
        solo_story.connect(room, self.publisher(room))
        choices = [pid for key, pid in ids.items() if key != room['scenario']['culprit']]
        self.assertEqual(solo_story.night_target(room, ids['elias'], choices), ids['mara'])

    def test_search_and_general_topic_questions_publish_relevant_material(self):
        identity, room = self.day()
        self.tell(identity, 'What do we know about the bell?')
        self.assertIn('mara-observation', room['story']['revealed'])
        self.tell(identity, 'Inspect the scene for evidence.')
        self.assertIn('splice', room['story']['revealed'])
        self.tell(identity, 'Search the scene for evidence.')
        self.assertIn('service', room['story']['revealed'])
        self.assertEqual(self.tell(identity, 'Search the scene for evidence.')['feedback'][:16], 'No new testimony')

    def test_context_has_only_the_current_characters_private_background(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        actors = [pid for pid, p in room['players'].items() if p['bot']]
        context = game.bot_context(room, actors[0])
        self.assertIn('secret', context['character'])
        for pid in actors[1:]:
            self.assertNotIn(room['players'][pid]['character']['secret'], repr(context))

    def test_replay_preserves_solution_but_clears_testimony_and_updates_ending(self):
        identity, room = self.day()
        roles = {pid: p['role'] for pid, p in room['players'].items()}
        self.tell(identity, 'Inspect the scene.')
        self.post('end', identity)
        self.assertNotIn('solution', self.post('state', identity)['scenario'])
        self.post('restart', identity)
        self.assertEqual(roles, {pid: p['role'] for pid, p in room['players'].items()})
        self.assertEqual(room['story']['revealed'], {})
        mafia = game.alive(room, 'mafia')[0]
        game.record_death(room, mafia, 'vote')
        game.check_win(room)
        state = self.post('state', identity)
        self.assertEqual(state['winner'], 'town')
        self.assertEqual(state['scenario']['solution'], room['scenario']['solution'])
        self.assertIn(room['players'][mafia]['name'], state['scenario']['consequences'])
        self.post('leave', identity)
        self.assertNotIn(identity['code'], game.rooms)

    def test_detective_is_protected_on_ordinary_solo_nights_regardless_of_round_number(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        self.post('start', identity)
        for _ in range(3):
            game.start_night(room)
            mafia = game.alive(room, 'mafia')[0]
            with self.assertRaises(game.Bad):
                game.mafia_vote(room, mafia, identity['pid'])
            game.run_bots(room)
            self.assertNotEqual(room['night']['victim'], identity['pid'])

    def test_online_rooms_keep_their_normal_workflow(self):
        identity = self.post('create', dict(name='Host', include_state=True))
        self.assertEqual(identity['state']['mode'], 'online')
        self.assertIsNone(identity['state']['scenario'])
        self.post('join', dict(code=identity['code'], name='Friend'))
        self.post('bot', dict(identity, count=1))
        self.post('start', identity)
        self.assertEqual(len(game.rooms[identity['code']]['players']), 3)
