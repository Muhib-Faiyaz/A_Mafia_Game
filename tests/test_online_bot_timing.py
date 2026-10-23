"""Fake-clock checks for visible online bot turns and a readable dawn."""
import unittest
from unittest.mock import patch
import app as game


class OnlineBotTimingTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.clock = patch.object(game.time, 'time', return_value=1000)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.client = game.app.test_client()
        self.host = self.post('create', dict(name='Watcher'))
        self.room = game.rooms[self.host['code']]
        self.room['settings'] = dict(mafia_count=1, special_roles=True)
        self.ids = {}
        for role, name in [('mafia', 'Mafia bot'), ('doctor', 'Doctor bot'), ('detective', 'Detective bot'),
                           ('town', 'Villager one'), ('town', 'Villager two'), ('town', 'Villager three')]:
            pid = game.add_player(self.room, name, bot=True)
            self.room['players'][pid]['role'] = role
            if role != 'town':
                self.ids[role] = pid
        self.room['players'][self.host['pid']]['role'] = 'town'
        self.room.update(round_id='timing-test', winner=None, death_events=[], notices=[], log=[])
        game.start_night(self.room)
        self.protect_host = False
        self.choices = patch.object(game.random, 'choice', side_effect=self.pick)
        self.choices.start()
        self.addCleanup(self.choices.stop)

    def post(self, route, body):
        response = self.client.post('/api/' + route, json=body)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def pick(self, candidates):
        if self.protect_host and self.host['pid'] in candidates:
            return self.host['pid']
        preferred = {'mafia': self.host['pid'], 'doctor': self.ids['doctor'], 'detective': self.ids['mafia']}
        choice = preferred.get(self.room.get('night_step')) if self.room['phase'] == 'night' else None
        return choice if choice in candidates else candidates[0]

    def poll(self, timestamp):
        self.now.return_value = timestamp
        return self.post('state', self.host)

    def finish_bot_night(self):
        self.poll(1005)
        self.poll(1010)
        return self.poll(1015)

    def test_each_living_bot_role_has_its_own_five_second_turn(self):
        self.assertGreaterEqual(game.BOT_TURN_DELAY, 5)
        state = self.poll(1000)
        self.assertEqual(state['night_step'], 'mafia')
        self.assertEqual(self.room['night']['mafia'], {})
        self.poll(1004.999)
        self.assertEqual(self.room['night']['mafia'], {})
        state = self.poll(1005)
        self.assertEqual(state['night_step'], 'doctor')
        self.assertEqual(self.room['step_started'], 1005)
        self.assertIsNone(self.room['night']['doctor'])
        self.poll(1009.999)
        self.assertIsNone(self.room['night']['doctor'])
        state = self.poll(1010)
        self.assertEqual(state['night_step'], 'detective')
        self.assertEqual(self.room['step_started'], 1010)
        self.assertIsNone(self.room['night']['detective'])
        self.poll(1014.999)
        self.assertIsNone(self.room['night']['detective'])
        state = self.poll(1015)
        self.assertEqual(state['phase'], 'day')
        self.assertEqual(self.room['night']['detective'], self.ids['mafia'])

    def test_late_poll_does_not_consume_all_new_bot_turns_at_once(self):
        # The old Mafia deadline can expire, but Doctor's newly entered turn
        # starts when it becomes visible, rather than inheriting elapsed time.
        state = self.poll(1000 + game.STEP + 100)
        self.assertEqual(state['night_step'], 'doctor')
        self.assertIsNone(self.room['night']['doctor'])
        entered = self.room['step_started']
        self.poll(entered + 4.999)
        self.assertIsNone(self.room['night']['doctor'])
        state = self.poll(entered + 5)
        self.assertEqual(state['night_step'], 'detective')
        self.assertIsNone(self.room['night']['detective'])

    def test_humans_without_bot_partners_can_confirm_immediately(self):
        for pid in self.ids.values():
            self.room['players'][pid]['bot'] = False
        self.post('act', dict(code=self.host['code'], pid=self.ids['mafia'], target=self.host['pid']))
        self.assertEqual(self.room['night_step'], 'doctor')
        self.post('act', dict(code=self.host['code'], pid=self.ids['doctor'], target=self.host['pid']))
        self.assertEqual(self.room['night_step'], 'detective')
        self.post('act', dict(code=self.host['code'], pid=self.ids['detective'], target=self.ids['mafia']))
        self.assertEqual(self.room['phase'], 'day')
        self.assertEqual(self.now.return_value, 1000)

    def test_mixed_mafia_turn_waits_for_bot_but_accepts_human_vote(self):
        human = game.add_player(self.room, 'Human partner')
        self.room['players'][human]['role'] = 'mafia'
        self.room['settings']['mafia_count'] = 2
        self.post('act', dict(code=self.host['code'], pid=human, target=self.host['pid']))
        self.assertEqual(self.room['night']['mafia'], {human: self.host['pid']})
        self.assertEqual(self.room['night_step'], 'mafia')
        self.poll(1004.999)
        self.assertNotIn(self.ids['mafia'], self.room['night']['mafia'])
        self.assertEqual(self.poll(1005)['night_step'], 'doctor')

    def test_original_human_timeout_still_progresses_when_no_action_is_taken(self):
        for pid in self.ids.values():
            self.room['players'][pid]['bot'] = False
        self.assertEqual(self.poll(1005)['night_step'], 'mafia')
        self.assertEqual(self.poll(1000 + game.STEP)['night_step'], 'doctor')
        self.assertEqual(self.poll(1000 + 2 * game.STEP)['night_step'], 'detective')
        state = self.poll(1000 + 3 * game.STEP)
        self.assertEqual(state['phase'], 'day')
        self.assertEqual(self.room['dawn'], 'Nobody was killed last night.')

    def test_dawn_survives_repeated_polls_before_all_bot_readiness(self):
        state = self.finish_bot_night()
        self.assertEqual(state['phase'], 'day')
        self.assertFalse(state['me']['alive'])
        self.assertEqual(len(state['death_events']), 1)
        self.assertEqual(state['death_events'][0]['player_id'], self.host['pid'])
        for timestamp in [1015, 1016, 1019.999]:
            state = self.poll(timestamp)
            self.assertEqual(state['phase'], 'day')
            self.assertEqual(self.room.get('discussion_ready', set()), set())
            self.assertEqual(self.room['votes'], {})
            self.assertEqual(len(state['death_events']), 1)
        state = self.poll(1020)
        self.assertNotEqual(state['phase'], 'day')
        self.assertEqual(sum(e['cause'] == 'night' for e in state['death_events']), 1)
        if state['phase'] == 'night':
            self.assertEqual(self.room['night_step'], 'mafia')
            self.assertEqual(self.room['night']['mafia'], {})

    def test_rescue_and_doctor_points_are_not_repeated_by_polling(self):
        self.protect_host = True
        state = self.finish_bot_night()
        self.assertTrue(state['me']['alive'])
        self.assertEqual(len(state['notices']), 1)
        self.assertEqual(state['notices'][0]['kind'], 'rescue')
        for timestamp in [1015, 1016, 1020, 1021]:
            state = self.poll(timestamp)
            self.assertEqual(state['phase'], 'day')
            self.assertEqual(len(state['notices']), 1)
        self.assertEqual(self.room['players'][self.ids['doctor']]['pending_points'], 1)


if __name__ == '__main__':
    unittest.main()
