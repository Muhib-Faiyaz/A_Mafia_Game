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

    def test_catalog_has_twenty_distinct_fully_authored_cases(self):
        self.assertEqual(len(solo_story.SCENARIOS), 20)
        self.assertEqual(len({s['id'] for s in solo_story.SCENARIOS}), 20)
        self.assertEqual(len({tuple(s['opening']) for s in solo_story.SCENARIOS}), 20)
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                self.assertEqual(len(case['opening']), 3)
                self.assertEqual(len(case['cast']), 6)
                self.assertEqual(len({p['name'].casefold() for p in case['cast']}), 6)
                self.assertTrue(all(p['alibi'] and p['secret'] and p['description'] for p in case['cast']))

    def test_every_case_starts_paused_and_private_then_runs_with_correct_roles(self):
        for case in solo_story.SCENARIOS:
            with self.subTest(case=case['id']):
                identity = self.create(case)
                room = game.rooms[identity['code']]
                state = identity['state']
                self.assertEqual(state['mode'], 'solo')
                self.assertEqual(state['scenario']['id'], case['id'])
                self.assertEqual(state['phase'], 'lobby')
                self.assertEqual(state['timer_total'], 0)
                self.assertEqual(len(state['players']), 7)
                serialized = json.dumps(state)
                for character in case['cast']:
                    self.assertNotIn(character['secret'], serialized)
                    self.assertNotIn(character['alibi'], serialized)
                with patch.object(game.time, 'time', return_value=time.time() + 600):
                    self.assertEqual(self.post('state', identity)['phase'], 'lobby')
                self.post('start', identity)
                roles = [p['role'] for p in room['players'].values()]
                self.assertEqual(room['players'][identity['pid']]['role'], 'detective')
                self.assertEqual(roles.count('mafia'), 2)
                self.assertEqual(roles.count('doctor'), 1)
                self.assertEqual(roles.count('town'), 3)
                self.assertEqual(room['night_step'], 'detective')
                self.assertNotEqual(room['night']['victim'], identity['pid'])
                self.assertIsNone(solo_story.public_case(room).get('epilogue'))

    def test_solo_rooms_reject_joining_and_cast_or_rule_changes(self):
        identity = self.create()
        self.post('join', dict(code=identity['code'], name='Outsider'), 400)
        self.post('bot', dict(identity, count=1), 400)
        self.post('settings', dict(identity, mafia_count=1), 400)
        self.assertEqual(len(game.rooms[identity['code']]['players']), 7)

    def test_alias_collision_preserves_cast_and_prose(self):
        state = self.create(name='Mara')['state']
        self.assertIn('Mara Vale', [p['name'] for p in state['scenario']['cast']])
        self.assertIn('Mara Vale', state['scenario']['opening'][0])
        self.assertEqual(len({p['name'] for p in state['players']}), 7)

    def test_last_case_can_be_excluded_without_mutating_catalog(self):
        with patch.object(solo_story.random, 'choice', side_effect=lambda cases: cases[0]):
            selected = solo_story.choose(solo_story.SCENARIOS[0]['id'])
        self.assertNotEqual(selected['id'], solo_story.SCENARIOS[0]['id'])
        selected['cast'][0]['name'] = 'Changed'
        self.assertNotEqual(solo_story.SCENARIOS[1]['cast'][0]['name'], 'Changed')

    def test_interview_secrets_are_private_until_spoken_and_affect_beliefs(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        self.post('start', identity)
        room.update(phase='day', discuss_until=time.time() + 1000)
        npc = next(pid for pid, p in room['players'].items() if p['bot'])
        actor = room['players'][npc]
        actor['brain'].update(day=1, posts=0, opened=True)
        room['bot_last_spoke'] = time.time()
        self.post('chat', dict(identity, text='@Mara, what are you hiding?'))
        state = self.post('state', identity)
        self.assertNotIn(actor['character']['secret'], json.dumps(state))
        room['players'][identity['pid']]['last'] = 0
        self.post('chat', dict(identity, text='@Mara, please be honest about your secret'))
        state = self.post('state', identity)
        self.assertTrue(any(c['n'] == 'Mara' and actor['character']['secret'] in c['t'] and c['disclosure'] for c in state['chat']))
        other = next(p for pid, p in room['players'].items() if p['bot'] and pid != npc)
        self.assertIn(npc, other['brain']['disclosed'])
        self.assertNotIn('secret', state['scenario']['cast'][0])

    def test_protected_opening_still_allows_normal_targeting_from_second_night(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        self.post('start', identity)
        self.assertNotEqual(room['night']['victim'], identity['pid'])
        game.start_night(room)
        mafia = game.alive(room, 'mafia')[0]
        game.mafia_vote(room, mafia, identity['pid'])
        self.assertEqual(room['night']['mafia'][mafia], identity['pid'])

    def test_direct_interviews_have_a_bounded_reserve_after_normal_chat_budget(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        self.post('start', identity)
        room.update(phase='day', discuss_until=time.time() + 1000)
        actor = next(p for p in room['players'].values() if p['name'] == 'Mara')
        actor['brain'].update(day=1, posts=bot_brain.MAX_POSTS, opened=True)
        for _ in range(8):
            room['players'][identity['pid']]['last'] = 0
            self.post('chat', dict(identity, text='@Mara, where were you before the first alarm?'))
        self.assertEqual(actor['brain']['posts'], bot_brain.MAX_POSTS + 4)

    def test_context_has_only_the_current_characters_private_background(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        actors = [pid for pid, p in room['players'].items() if p['bot']]
        context = game.bot_context(room, actors[0])
        self.assertIn('secret', context['character'])
        for pid in actors[1:]:
            self.assertNotIn(room['players'][pid]['character']['secret'], repr(context))

    def test_story_deaths_endings_and_leaving_use_the_selected_case(self):
        identity = self.create()
        room = game.rooms[identity['code']]
        self.post('start', identity)
        npc = next(pid for pid, p in room['players'].items() if p['bot'])
        game.record_death(room, npc, 'vote')
        self.assertIn('placed under guard', room['death_events'][-1]['story'])
        self.post('end', identity)
        self.assertIn('suspended', self.post('state', identity)['scenario']['epilogue'])
        self.post('leave', identity)
        self.assertNotIn(identity['code'], game.rooms)

    def test_online_rooms_keep_their_normal_workflow(self):
        identity = self.post('create', dict(name='Host', include_state=True))
        self.assertEqual(identity['state']['mode'], 'online')
        self.assertIsNone(identity['state']['scenario'])
        self.post('join', dict(code=identity['code'], name='Friend'))
        self.post('bot', dict(identity, count=1))
        self.post('start', identity)
        self.assertEqual(len(game.rooms[identity['code']]['players']), 3)


class StoryReplyTests(unittest.TestCase):
    def test_alibi_is_explicitly_an_account_of_the_first_alarm(self):
        profile = solo_story.SCENARIOS[0]['cast'][0]
        context = dict(self='npc', character=dict(profile, relationship='A friend vouched for me.'), players=[dict(id='reader', name='Reader')])
        pending = dict(intent=dict(addressed='npc', question=True), message=dict(t='@Mara, where were you last night?', speaker='reader'))
        text, disclosed = solo_story.roleplay_reply(bot_brain.new_brain(), context, pending, 'Fallback')
        self.assertIn('before the first alarm', text)
        self.assertIn(profile['alibi'], text)
        self.assertFalse(disclosed)
        self.assertNotIn(profile['secret'], text)
