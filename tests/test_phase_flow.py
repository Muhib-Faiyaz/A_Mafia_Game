import unittest
from unittest.mock import patch
import app as game


class PhaseFlowTests(unittest.TestCase):
    def setUp(self):
        # The dedicated timing suite covers real delays; these fixtures exercise actions.
        delay = patch.object(game, 'BOT_TURN_DELAY', 0, create=True)
        delay.start()
        self.addCleanup(delay.stop)
        game.rooms.clear()
        self.client = game.app.test_client()
        self.host = self.post('create', {'name': 'Host'})
        self.users = [self.host] + [self.post('join', {'code': self.host['code'], 'name': f'Guest {i}'}) for i in range(6)]
        self.post('settings', dict(self.host, mafia_count=2, special_roles=True))
        self.post('start', self.host)
        self.room = game.rooms[self.host['code']]
        self.players = self.room['players']
        self.mafia = [u for u in self.users if self.players[u['pid']]['role'] == 'mafia']
        self.doctor = next(u for u in self.users if self.players[u['pid']]['role'] == 'doctor')
        self.detective = next(u for u in self.users if self.players[u['pid']]['role'] == 'detective')
        self.villager = next(u for u in self.users if self.players[u['pid']]['role'] == 'town' and u != self.host)

    def post(self, route, data, status=200):
        response = self.client.post('/api/' + route, json=data)
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def reach_detective(self):
        target = self.villager['pid']
        for user in self.mafia:
            self.post('act', dict(user, target=target))
        self.assertEqual(self.room['night_step'], 'doctor')
        self.post('act', dict(self.doctor, target=target))
        self.assertEqual(self.room['night_step'], 'detective')

    def reach_discussion(self):
        self.reach_detective()
        self.post('act', dict(self.detective, target=self.mafia[0]['pid']))
        self.assertEqual(self.room['phase'], 'day')
        self.assertTrue(game.discussing(self.room))

    def test_immediate_correct_result_is_private_and_contains_persuasion_rule(self):
        self.reach_detective()
        response = self.post('act', dict(self.detective, target=self.mafia[0]['pid'], include_state=True))
        result = response['state']['investigation']
        self.assertTrue(result['correct'])
        self.assertEqual(result['name'], self.players[self.mafia[0]['pid']]['name'])
        self.assertIn('Do not directly reveal', result['reminder'])
        self.assertIn('Convince the others', result['reminder'])
        self.assertIn(result['reminder'], response['state']['notes'][0])
        self.assertTrue(all(p['score'] == 0 and p['round_points'] == 0 for p in response['state']['players']))
        for user in self.users:
            if user != self.detective:
                state = self.post('state', user)
                self.assertIsNone(state['investigation'])
                self.assertEqual(state['notes'], [])
                self.assertFalse(any(result['reminder'] in entry['t'] for entry in state['chat'] + state['log']))
        self.assertEqual(self.players[self.detective['pid']]['pending_points'], 0)

    def test_wrong_result_and_only_one_investigation_each_night(self):
        self.reach_detective()
        self.post('act', dict(self.detective, target=self.detective['pid']), 400)
        state = self.post('act', dict(self.detective, target=self.villager['pid'], include_state=True))['state']
        self.assertFalse(state['investigation']['correct'])
        self.assertIn('not Mafia', state['notes'][0])
        self.post('act', dict(self.detective, target=self.mafia[0]['pid']), 400)
        self.assertEqual(len(self.players[self.detective['pid']]['notes']), 1)

    def test_confirmed_mafia_target_is_final_and_every_role_advances(self):
        target = self.villager['pid']
        self.post('act', dict(self.mafia[0], target=target))
        self.assertEqual(self.room['night_step'], 'mafia')
        self.post('act', dict(self.mafia[0], target=self.doctor['pid']), 400)
        self.post('act', dict(self.mafia[1], target=target))
        self.assertEqual(self.room['night_step'], 'doctor')
        self.post('act', dict(self.doctor, target=target))
        self.assertEqual(self.room['night_step'], 'detective')
        self.post('act', dict(self.doctor, target=self.doctor['pid']), 400)
        self.post('act', dict(self.detective, target=self.mafia[0]['pid']))
        self.assertEqual(self.room['phase'], 'day')

    def test_no_actions_use_existing_timers_instead_of_host_skip(self):
        for role in ['mafia', 'doctor', 'detective']:
            self.assertEqual(self.room['night_step'], role)
            state = self.post('state', self.host)
            self.assertEqual(state['timer_total'], game.STEP)
            self.post('skip', self.host, 400)
            self.room['step_until'] = 0
            self.post('state', self.host)
        self.assertEqual(self.room['phase'], 'day')
        self.assertTrue(all(p['alive'] for p in self.players.values()))
        self.assertIsNone(self.post('state', self.detective)['investigation'])
        self.assertEqual(self.post('state', self.host)['timer_total'], game.DISCUSS)
        self.room['discuss_until'] = 0
        state = self.post('state', self.host)
        self.assertTrue(state['voting'])
        self.assertTrue(any('Voting is now open' in c['t'] for c in state['chat']))

    def test_readiness_needs_every_living_player_and_updates_chat_once(self):
        self.reach_discussion()
        state = self.post('proceed', dict(self.host, include_state=True))['state']
        self.assertEqual(state['discussion'], {'ready': 1, 'total': 7, 'voted': True})
        self.assertFalse(state['voting'])
        count = len(self.room['chat'])
        self.post('proceed', self.host)
        self.assertEqual(len(self.room['chat']), count)
        self.assertTrue(any('Host voted to proceed' in c['t'] for c in state['chat']))
        for user in self.users[1:-1]:
            self.post('proceed', user)
            self.assertTrue(game.discussing(self.room))
        final = self.post('proceed', dict(self.users[-1], include_state=True))['state']
        self.assertTrue(final['voting'])
        self.assertEqual(final['discussion']['ready'], 7)
        self.assertTrue(any('(7/7 ready)' in c['t'] for c in final['chat']))
        for user in self.users:
            self.post('vote', dict(user, target='skip'))
        self.assertEqual(self.room['phase'], 'night')
        self.assertEqual(self.room['discussion_ready'], set())

    def test_readiness_excludes_eliminated_players_and_old_skip_is_not_a_bypass(self):
        self.reach_discussion()
        self.players[self.villager['pid']]['alive'] = False
        self.post('proceed', self.villager, 400)
        self.post('skip', self.host)
        self.assertTrue(game.discussing(self.room))
        for user in self.users:
            if user not in (self.villager, self.host):
                self.post('proceed', user)
        self.assertFalse(game.discussing(self.room))
        self.assertEqual(self.post('state', self.host)['discussion']['total'], 6)

    def test_partial_readiness_still_opens_voting_on_timeout(self):
        self.reach_discussion()
        self.post('proceed', self.users[1])
        self.room['discuss_until'] = 0
        self.assertTrue(self.post('state', self.host)['voting'])

    def test_bots_mark_ready_without_blocking_the_human(self):
        self.reach_discussion()
        for user in self.users[1:]:
            self.players[user['pid']]['bot'] = True
        state = self.post('state', self.host)
        self.assertEqual(state['discussion']['ready'], 6)
        self.assertFalse(state['voting'])
        self.assertTrue(self.post('proceed', dict(self.host, include_state=True))['state']['voting'])

    def test_eliminated_special_roles_do_not_hold_up_the_night(self):
        self.players[self.doctor['pid']]['alive'] = False
        self.players[self.detective['pid']]['alive'] = False
        for user in self.mafia:
            self.post('act', dict(user, target=self.villager['pid']))
        self.assertNotEqual(self.room['phase'], 'night')

    def test_new_round_clears_investigation_and_readiness(self):
        self.reach_discussion()
        self.post('proceed', self.host)
        self.post('restart', self.host)
        state = self.post('state', self.detective)
        self.assertIsNone(state['investigation'])
        self.assertEqual(state['notes'], [])
        self.assertEqual(state['discussion']['ready'], 0)
        self.assertTrue(all(not p['investigated'] for p in self.players.values()))
