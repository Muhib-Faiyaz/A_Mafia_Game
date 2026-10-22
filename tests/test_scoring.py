import json
import unittest
import app as game


class ScoringTests(unittest.TestCase):
    def setUp(self):
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
        self.villager = next(u for u in self.users if self.players[u['pid']]['role'] == 'town')

    def post(self, route, body):
        response = self.client.post('/api/' + route, json=body)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def saved_night(self, victim=None, investigation=None):
        victim = victim or self.villager['pid']
        investigation = investigation or self.mafia[0]['pid']
        for user in self.mafia:
            self.post('act', dict(user, target=victim))
        self.post('act', dict(self.doctor, target=victim))
        self.post('act', dict(self.detective, target=investigation))

    def test_actions_hidden_then_settled_once_on_end(self):
        self.saved_night()
        for user in self.users:
            state = self.post('state', user)
            self.assertTrue(all(p['score'] == 0 and p['round_points'] == 0 for p in state['players']))
            self.assertNotIn('pending_points', json.dumps(state))
            self.assertNotIn('investigated', json.dumps(state))
        self.post('end', self.host)
        self.assertEqual(self.players[self.doctor['pid']]['score'], 1)
        self.assertEqual(self.players[self.detective['pid']]['score'], 0)
        self.assertEqual(self.players[self.mafia[0]['pid']]['score'], 0)
        game.settle_scores(self.room)
        self.post('state', self.host)
        self.assertEqual(self.players[self.doctor['pid']]['score'], 1)

    def test_rescue_story_keeps_doctor_identity_secret(self):
        self.saved_night()
        state = self.post('state', self.villager)
        event = state['notices'][0]
        self.assertEqual(event['kind'], 'rescue')
        self.assertEqual(event['name'], self.players[self.villager['pid']]['name'])
        self.assertNotIn(self.players[self.doctor['pid']]['name'], event['story'])
        self.assertNotIn(self.doctor['pid'], json.dumps(event))
        self.assertEqual(state['death_events'], [])
        self.assertIsNone(next(p for p in state['players'] if p['id'] == self.doctor['pid'])['role'])
        self.assertTrue(any(entry['t'] == event['story'] for entry in state['log']))

    def test_repeat_rescues_count_but_repeat_identifications_do_not(self):
        self.saved_night()
        self.room['discuss_until'] = 0
        self.post('tally', self.host)
        self.saved_night()
        game.resolve_night(self.room)  # Retries must not duplicate points or notices.
        self.post('end', self.host)
        self.assertEqual(self.players[self.doctor['pid']]['score'], 2)
        self.assertEqual(self.players[self.detective['pid']]['score'], 0)
        self.assertEqual(len(self.room['notices']), 2)
        self.assertNotEqual(self.room['notices'][0]['story'], self.room['notices'][1]['story'])

    def test_new_identification_and_self_rescue(self):
        self.saved_night(victim=self.doctor['pid'])
        self.room['discuss_until'] = 0
        self.post('tally', self.host)
        self.saved_night(investigation=self.mafia[1]['pid'])
        self.post('end', self.host)
        self.assertEqual(self.players[self.doctor['pid']]['score'], 2)
        self.assertEqual(self.players[self.detective['pid']]['score'], 0)

    def test_wrong_identification_and_no_attack_do_not_score(self):
        self.room['step_until'] = 0
        self.post('state', self.host)
        self.post('act', dict(self.doctor, target=self.villager['pid']))
        self.post('act', dict(self.detective, target=self.villager['pid']))
        self.post('end', self.host)
        self.assertTrue(all(p['score'] == 0 for p in self.players.values()))
        self.assertEqual(self.room['notices'], [])

    def test_town_win_rewards_only_surviving_town_members(self):
        self.saved_night()
        self.players[self.villager['pid']]['alive'] = False
        for user in self.mafia:
            self.players[user['pid']]['alive'] = False
        self.assertTrue(game.check_win(self.room))
        self.assertEqual(self.players[self.doctor['pid']]['score'], 2)
        self.assertEqual(self.players[self.detective['pid']]['score'], 2)
        self.assertEqual(self.players[self.villager['pid']]['score'], 0)
        self.assertTrue(all(self.players[u['pid']]['score'] == 0 for u in self.mafia))
        game.check_win(self.room)
        self.assertEqual(self.players[self.doctor['pid']]['score'], 2)

    def test_mafia_team_win_rewards_each_mafia_even_eliminated(self):
        self.players[self.mafia[0]['pid']]['alive'] = False
        for p in self.players.values():
            if p['role'] != 'mafia':
                p['alive'] = False
        self.players[self.villager['pid']]['alive'] = True
        self.assertTrue(game.check_win(self.room))
        for user in self.mafia:
            self.assertEqual(self.players[user['pid']]['score'], 1)
        self.assertEqual(self.players[self.villager['pid']]['score'], 0)

    def town_win(self):
        for user in self.mafia:
            self.players[user['pid']]['alive'] = False
        self.assertTrue(game.check_win(self.room))

    def test_survival_without_investigating_gets_one_on_town_win(self):
        self.town_win()
        self.assertEqual(self.players[self.detective['pid']]['score'], 1)

    def test_wrong_identification_gets_one_on_surviving_town_win(self):
        self.saved_night(investigation=self.villager['pid'])
        self.town_win()
        self.assertEqual(self.players[self.detective['pid']]['score'], 1)

    def test_two_correct_identifications_are_capped_at_two_for_surviving_winner(self):
        self.saved_night()
        self.room['discuss_until'] = 0
        self.post('tally', self.host)
        self.saved_night(investigation=self.mafia[1]['pid'])
        self.town_win()
        detective = self.players[self.detective['pid']]
        self.assertEqual(detective['score'], 2)
        game.settle_scores(self.room)
        self.assertEqual(detective['score'], 2)
        self.assertEqual(detective['round_points'], 2)

    def test_eliminated_detective_gets_zero_despite_correct_identification(self):
        self.saved_night()
        self.players[self.detective['pid']]['alive'] = False
        self.town_win()
        self.assertEqual(self.players[self.detective['pid']]['score'], 0)

    def test_mafia_win_gives_surviving_detective_zero(self):
        self.saved_night()
        for player in self.players.values():
            player['alive'] = player['role'] in ('mafia', 'detective')
        self.assertTrue(game.check_win(self.room))
        self.assertEqual(self.room['winner'], 'mafia')
        self.assertEqual(self.players[self.detective['pid']]['score'], 0)

    def test_scores_follow_player_identity_across_restart_and_reset(self):
        self.saved_night()
        self.post('end', self.host)
        before = {pid: (p['name'], p['score']) for pid, p in self.players.items()}
        self.post('restart', self.host)
        self.assertEqual(before, {pid: (p['name'], p['score']) for pid, p in self.players.items()})
        self.assertTrue(all(p['pending_points'] == 0 and p['round_points'] == 0 for p in self.players.values()))
        self.post('end', self.host)
        self.post('reset', self.host)
        self.assertEqual(before, {pid: (p['name'], p['score']) for pid, p in self.players.items()})
        new_room = self.post('create', {'name': 'Host'})
        self.assertEqual(self.post('state', new_room)['players'][0]['score'], 0)

    def test_restart_unfinished_game_discards_unpublished_points(self):
        self.saved_night()
        self.post('restart', self.host)
        self.assertTrue(all(p['score'] == 0 and p['pending_points'] == 0 for p in self.players.values()))


if __name__ == '__main__':
    unittest.main()
