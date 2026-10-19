import unittest
from unittest.mock import patch
import app as game


class GameTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.client = game.app.test_client()
        self.host = self.post('create', {'name': 'Host'})
        self.users = [self.host]
        for i in range(6):
            self.users.append(self.post('join', {'code': self.host['code'], 'name': f'Player {i}'}))
        self.room = game.rooms[self.host['code']]

    def post(self, route, data, status=200):
        response = self.client.post('/api/' + route, json=data)
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def start(self, special=False, count=2):
        self.post('settings', dict(self.host, special_roles=special, mafia_count=count))
        self.post('start', self.host)
        self.mafia = [u for u in self.users if self.room['players'][u['pid']]['role'] == 'mafia']
        self.town = [u for u in self.users if self.room['players'][u['pid']]['role'] != 'mafia']

    def test_settings_and_roles(self):
        self.start()
        self.assertEqual(len(self.mafia), 2)
        self.assertEqual({p['role'] for p in self.room['players'].values()}, {'mafia', 'town'})

    def test_special_roles(self):
        self.start(True)
        roles = [p['role'] for p in self.room['players'].values()]
        self.assertIn('doctor', roles)
        self.assertIn('detective', roles)

    def test_settings_permissions_validation_and_departures(self):
        self.post('settings', dict(self.users[1], mafia_count=1), 400)
        for count in [0, 4, True, '2']:
            self.post('settings', dict(self.host, mafia_count=count), 400)
        self.post('settings', dict(self.host, mafia_count=3))
        self.post('leave', self.users[-1])
        self.post('start', self.host, 400)

    def test_unanimous_votes_end_timer_and_kill(self):
        self.start()
        self.post('skip', self.host, 400)
        target = self.town[0]['pid']
        self.post('act', dict(self.mafia[0], target=target))
        self.assertEqual(self.room['phase'], 'night')
        name = self.room['players'][target]['name']
        self.post('chat', dict(self.mafia[1], channel='mafia', text='/vote ' + name))
        self.assertEqual(self.room['phase'], 'day')
        self.assertFalse(self.room['players'][target]['alive'])

    def test_split_votes_choose_from_all_distinct_targets(self):
        self.start(count=3)
        a, b = [u['pid'] for u in self.town[:2]]
        with patch.object(game.random, 'choice', return_value=b) as choose:
            for user, target in zip(self.mafia, [a, a, b]):
                self.post('act', dict(user, target=target))
            self.assertEqual(set(choose.call_args.args[0]), {a, b})
        self.assertFalse(self.room['players'][b]['alive'])
        self.assertTrue(self.room['players'][a]['alive'])

    def test_timeout_partial_and_empty_ballots(self):
        self.start()
        self.post('act', dict(self.mafia[0], target=self.town[0]['pid']))
        self.room['step_until'] = 0
        self.post('state', self.host)
        self.assertFalse(self.room['players'][self.town[0]['pid']]['alive'])
        game.start_night(self.room)
        before = len(game.alive(self.room))
        self.room['step_until'] = 0
        self.post('state', self.host)
        self.assertEqual(len(game.alive(self.room)), before)
        self.assertEqual(self.room['phase'], 'day')

    def test_private_chat_and_vote_access(self):
        self.start()
        self.post('chat', dict(self.mafia[0], channel='mafia', text='Secret plan'))
        state = self.post('state', self.town[0])
        self.assertEqual(state['mafia_chat'], [])
        self.assertFalse(any(c['t'] == 'Secret plan' for c in state['chat']))
        self.assertTrue(any(c['t'] == 'Secret plan' for c in self.post('state', self.mafia[1])['mafia_chat']))
        self.post('chat', dict(self.town[0], channel='mafia', text='Intrusion'), 400)
        self.post('act', dict(self.town[0], target=self.mafia[0]['pid']), 400)
        self.post('act', dict(self.mafia[0], target=self.mafia[1]['pid']), 400)
        self.room['step_until'] = 0
        self.post('state', self.host)
        self.room['players'][self.mafia[0]['pid']]['last'] = 0
        self.post('chat', dict(self.mafia[0], channel='town', text='Public message'))
        self.assertTrue(any(c['t'] == 'Public message' for c in self.post('state', self.town[0])['chat']))

    def test_doctor_can_save_mafia_target(self):
        self.start(True)
        target = self.town[0]['pid']
        for user in self.mafia:
            self.post('act', dict(user, target=target))
        self.assertEqual(self.room['night_step'], 'doctor')
        doctor = next(u for u in self.users if self.room['players'][u['pid']]['role'] == 'doctor')
        self.post('act', dict(doctor, target=target))
        self.post('skip', self.host)
        self.post('skip', self.host)
        self.assertTrue(self.room['players'][target]['alive'])
        self.assertEqual(self.room['phase'], 'day')

    def test_default_is_one_and_maximum_is_three(self):
        self.assertEqual(self.room['settings']['mafia_count'], 1)
        self.post('settings', dict(self.host, mafia_count=None))
        self.assertEqual(self.room['settings']['mafia_count'], 1)
        self.post('start', self.host)
        self.assertEqual(len(game.alive(self.room, 'mafia')), 1)

    def test_two_mafia_split_votes_lock_target_until_dawn(self):
        self.start(True)
        a, b = [u['pid'] for u in self.town[:2]]
        with patch.object(game.random, 'choice', return_value=b) as choice:
            self.post('act', dict(self.mafia[0], target=a))
            self.post('act', dict(self.mafia[1], target=b))
            self.assertEqual(set(choice.call_args.args[0]), {a, b})
            choice.assert_called_once()
        self.assertEqual(self.room['night']['victim'], b)
        self.assertEqual(self.room['night_step'], 'doctor')
        self.post('skip', self.host)
        self.post('skip', self.host)
        self.assertFalse(self.room['players'][b]['alive'])
        self.assertTrue(self.room['players'][a]['alive'])

    def test_two_mafia_split_votes_kill_without_special_roles(self):
        self.start(False)
        a, b = [u['pid'] for u in self.town[:2]]
        self.post('act', dict(self.mafia[0], target=a))
        self.post('act', dict(self.mafia[1], target=b))
        dead = {i for i, p in self.room['players'].items() if not p['alive']}
        self.assertEqual(len(dead), 1)
        self.assertTrue(dead <= {a, b})
        self.assertEqual(self.room['phase'], 'day')

    def test_end_restart_permissions_and_state(self):
        self.start()
        old_round = self.room['round_id']
        self.post('end', self.users[1], 400)
        self.post('restart', self.users[1], 400)
        self.post('end', self.host)
        state = self.post('state', self.host)
        self.assertTrue(state['ended'])
        self.assertEqual(state['phase'], 'over')
        self.assertIsNone(state['winner'])
        self.assertTrue(all(p['role'] for p in state['players']))
        self.post('act', dict(self.mafia[0], target=self.town[0]['pid']), 400)
        self.post('restart', self.host)
        self.assertEqual(self.room['phase'], 'night')
        self.assertNotEqual(self.room['round_id'], old_round)
        self.assertFalse(self.room['ended'])
        self.assertEqual(len(self.room['players']), 7)
        self.assertEqual(len(game.alive(self.room)), 7)
        self.assertEqual(self.room['night']['mafia'], {})
        self.assertEqual(self.room['votes'], {})
        self.assertEqual(self.room['day'], 1)

    def test_restart_midgame_and_return_to_lobby(self):
        self.start()
        self.room['players'][self.town[0]['pid']]['alive'] = False
        self.post('restart', self.host)
        self.assertEqual(len(game.alive(self.room)), 7)
        self.post('end', self.host)
        self.post('reset', self.host)
        self.assertEqual(self.room['phase'], 'lobby')
        self.assertEqual(self.room['settings']['mafia_count'], 2)
        self.assertTrue(all(p['role'] is None for p in self.room['players'].values()))

    def test_death_story_is_shared_and_only_published_at_dawn(self):
        self.start(True)
        target = self.town[0]['pid']
        for user in self.mafia:
            self.post('act', dict(user, target=target))
        self.assertEqual(self.post('state', self.host)['death_events'], [])
        self.post('skip', self.host)
        self.post('skip', self.host)
        event = self.post('state', self.host)['death_events'][0]
        self.assertEqual(event['player_id'], target)
        self.assertEqual(event['cause'], 'night')
        self.assertIn(event['tone'], {'sad', 'goofy', 'eerie'})
        self.assertIn(event['name'], event['story'])
        for user in self.users:
            self.assertEqual(self.post('state', user)['death_events'], [event])
        self.assertTrue(any(entry['t'] == event['story'] for entry in self.room['log']))
        self.post('restart', self.host)
        self.assertEqual(self.post('state', self.host)['death_events'], [])

    def test_saved_players_have_no_death_notification(self):
        self.start(True)
        target = self.town[0]['pid']
        for user in self.mafia:
            self.post('act', dict(user, target=target))
        doctor = next(u for u in self.users if self.room['players'][u['pid']]['role'] == 'doctor')
        self.post('act', dict(doctor, target=target))
        self.post('skip', self.host)
        self.post('skip', self.host)
        self.assertEqual(self.post('state', self.host)['death_events'], [])

    def test_vote_elimination_has_its_own_story_and_no_duplicate(self):
        self.start(False)
        self.room['step_until'] = 0
        self.post('state', self.host)
        self.post('skip', self.host)
        target = self.town[0]['pid']
        self.post('vote', dict(self.mafia[0], target=target))
        self.post('tally', self.host)
        event = self.room['death_events'][0]
        self.assertEqual(event['cause'], 'vote')
        self.assertEqual(event['player_id'], target)
        game.record_death(self.room, target, 'vote')
        self.assertEqual(len(self.room['death_events']), 1)

    def test_all_story_templates_accept_player_names(self):
        self.start(False)
        for cause, templates in game.DEATH_STORIES.items():
            for index, (tone, template) in enumerate(templates):
                target = self.town[0]['pid']
                self.room['players'][target]['alive'] = True
                self.room['players'][target]['name'] = '<Alex & Sam>'
                with patch.object(game.random, 'randrange', return_value=index):
                    game.record_death(self.room, target, cause)
                event = self.room['death_events'][-1]
                self.assertEqual(event['story'], template.format(name='<Alex & Sam>'))
                self.assertEqual(event['tone'], tone)


if __name__ == '__main__':
    unittest.main()
