"""Case completion and replacement must preserve the invited Detective team."""
import copy
import time
import unittest
from unittest.mock import patch

import app as game
import solo_story


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.client = game.app.test_client()

    def post(self, route, identity, status=200, client=None):
        response = (client or self.client).post('/api/' + route, json=identity)
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def team(self, lead_name='Lead', friends=('One', 'Two')):
        lead = self.post('solo', dict(name=lead_name, scenario_id=solo_story.SCENARIOS[0]['id']))
        room = game.rooms[lead['code']]
        invite = dict(code=lead['code'], invite=room['invite_token'])
        members = [self.post('solo-join', dict(invite, name=name)) for name in friends]
        return lead, members, room

    def test_natural_town_and_mafia_endings_keep_team_sessions_and_dossier(self):
        for winner in ('town', 'mafia'):
            with self.subTest(winner=winner):
                lead, friends, room = self.team()
                self.post('start', lead)
                for player in room['players'].values():
                    if winner == 'town' and player['role'] == 'mafia':
                        player['alive'] = False
                    elif winner == 'mafia' and player['role'] != 'mafia':
                        player['alive'] = False
                self.assertTrue(game.check_win(room))
                for identity in [lead] + friends:
                    state = self.post('state', identity, client=game.app.test_client())
                    self.assertEqual(state['phase'], 'over')
                    self.assertEqual(state['winner'], winner)
                    self.assertEqual(state['team']['count'], 2)
                    self.assertIn('solution', state['scenario'])
                self.post('solo-next', dict(lead, scenario_id=solo_story.SCENARIOS[1]['id']))
                self.assertTrue(self.post('state', friends[0])['me']['alive'])
                game.rooms.clear()

    def test_host_end_replay_and_return_to_briefing_keep_friends(self):
        lead, friends, room = self.team()
        self.post('start', lead)
        first_round = room['round_id']
        self.post('end', lead)
        self.assertEqual(self.post('state', friends[0])['phase'], 'over')
        self.post('restart', lead)
        self.assertNotEqual(room['round_id'], first_round)
        self.assertEqual(self.post('state', friends[1])['team']['count'], 2)
        self.post('end', lead)
        self.post('reset', lead)
        self.assertEqual(self.post('state', friends[1])['phase'], 'lobby')

    def test_next_case_preserves_identities_invitation_chat_and_lead_score(self):
        lead, friends, room = self.team()
        invite_token = room['invite_token']
        old_npcs = set(room['players']) - {lead['pid']}
        self.post('team-chat', dict(friends[0], text='Our plan stays with the team.'))
        self.post('start', lead)
        self.post('end', lead)
        room['players'][lead['pid']]['score'] = 4
        room['story']['claims']['old'] = dict(target='old', stance='suspect')
        selected = self.post('solo-next', dict(lead, scenario_id=solo_story.SCENARIOS[1]['id'], include_state=True))
        self.assertEqual((selected['code'], selected['pid']), (lead['code'], lead['pid']))
        self.assertIs(game.rooms[lead['code']], room)
        self.assertEqual(room['invite_token'], invite_token)
        self.assertEqual(set(room['friends']), {f['pid'] for f in friends})
        self.assertTrue(old_npcs.isdisjoint(room['players']))
        self.assertEqual(room['players'][lead['pid']]['score'], 4)
        self.assertEqual(room['story']['claims'], {})
        self.assertEqual(selected['state']['phase'], 'lobby')
        self.assertIsNone(selected['state']['round_id'])
        self.assertEqual(selected['state']['death_events'], [])
        self.assertNotIn('solution', selected['state']['scenario'])
        for identity in friends:
            state = self.post('state', identity, client=game.app.test_client())
            self.assertEqual(state['scenario']['id'], solo_story.SCENARIOS[1]['id'])
            self.assertTrue(any(m['t'] == 'Our plan stays with the team.' for m in state['team_chat']))
            self.assertEqual(next(m for m in state['team_chat'] if m['t'] == 'Our plan stays with the team.')['speaker'], friends[0]['pid'])
        self.post('leave', friends[0])
        replacement = self.post('solo-join', dict(code=lead['code'], invite=invite_token, name='Replacement'))
        self.assertIn(replacement['pid'], room['friends'])
        self.post('start', lead)
        self.assertEqual(self.post('state', friends[1])['night_step'], 'mafia')

    def test_next_case_renames_cast_colliding_with_lead_and_friend_aliases(self):
        case = solo_story.SCENARIOS[1]
        lead_name, other_name = case['cast'][0]['name'], case['cast'][1]['name']
        lead, friends, room = self.team(lead_name, (lead_name + ' Vale', other_name))
        before = copy.deepcopy(case)
        self.post('solo-next', dict(lead, scenario_id=case['id']))
        names = [p['name'].casefold() for p in room['players'].values()] + [f['name'].casefold() for f in room['friends'].values()]
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(room['scenario']['cast'][0]['name'], lead_name + ' Vale 2')
        self.assertEqual(room['scenario']['cast'][1]['name'], other_name + ' Vale')
        self.assertEqual(case, before)
        self.post('start', lead)
        self.assertEqual(self.post('state', friends[1])['team']['count'], 2)

    def test_next_case_is_lead_only_and_rejects_active_or_invalid_selection(self):
        lead, friends, room = self.team()
        npc = next(pid for pid in room['players'] if pid != lead['pid'])
        self.post('solo-next', friends[0], 403)
        self.post('solo-next', dict(code=lead['code'], pid=npc), 403)
        original = room['scenario']['id']
        old_players = set(room['players'])
        self.post('solo-next', dict(lead, scenario_id='missing'), 400)
        self.assertEqual(room['scenario']['id'], original)
        self.assertEqual(set(room['players']), old_players)
        self.post('start', lead)
        self.post('solo-next', dict(lead, scenario_id='random'), 400)
        self.post('end', lead)
        self.post('solo-next', dict(lead, scenario_id='random'))
        self.assertNotEqual(room['scenario']['id'], original)
        online = self.post('create', dict(name='Host'))
        self.post('solo-next', online, 403)

    def test_friend_leave_only_removes_that_friend_and_explicit_lead_leave_closes_room(self):
        lead, friends, room = self.team()
        self.post('leave', friends[0])
        self.post('state', friends[0], 404)
        self.assertEqual(self.post('state', friends[1])['team']['count'], 1)
        self.post('leave', lead)
        self.post('state', friends[1], 404)
        self.assertNotIn(lead['code'], game.rooms)

    def test_reconnecting_friend_refreshes_idle_room_expiration(self):
        lead, friends, room = self.team()
        room['t'] = time.time() - 7 * 3600
        self.post('state', friends[0], client=game.app.test_client())
        self.post('create', dict(name='Other host'))
        self.assertIn(lead['code'], game.rooms)
        room['t'] = time.time() - 7 * 3600
        self.post('create', dict(name='Another host'))
        self.post('state', friends[1], 404)

    def test_online_end_and_restart_keep_each_player_identity(self):
        host = self.post('create', dict(name='Host'))
        guests = [self.post('join', dict(code=host['code'], name='Guest ' + str(i))) for i in range(2)]
        self.post('start', host)
        self.post('end', host)
        for identity in [host] + guests:
            self.assertEqual(self.post('state', identity, client=game.app.test_client())['phase'], 'over')
        self.post('restart', host)
        self.assertEqual(set(game.rooms[host['code']]['players']), {i['pid'] for i in [host] + guests})


    def test_tutorial_uses_real_manual_turns_has_no_first_night_death_or_scores(self):
        identity = self.post('tutorial', dict(name='Learner', include_state=True))
        room = game.rooms[identity['code']]
        self.assertTrue(identity['state']['tutorial'])
        self.assertEqual(identity['state']['scenario']['id'], 'practice-dispatch')
        self.assertNotIn('practice-dispatch', {s['id'] for s in self.client.get('/api/stories').get_json()['stories']})
        self.post('start', identity)
        with patch.object(game.time, 'time', return_value=time.time() + 10000):
            self.assertEqual(self.post('state', identity)['night_step'], 'mafia')
        self.post('solo-proceed', identity)
        self.assertIsNone(room['night']['victim'])
        self.post('solo-proceed', identity)
        culprit = solo_story.cast_ids(room)[room['scenario']['culprit']]
        self.post('act', dict(identity, target=culprit))
        self.post('solo-proceed', identity)
        self.assertEqual(room['phase'], 'day')
        self.assertEqual(room['death_events'], [])
        for player in room['players'].values():
            player['pending_points'] = 2
        room['players'][culprit]['alive'] = False
        self.assertTrue(game.check_win(room))
        self.assertTrue(all(p['score'] == 0 and p['round_points'] == 0 and p['pending_points'] == 0 for p in room['players'].values()))
        self.post('solo-next', dict(identity, scenario_id=solo_story.SCENARIOS[0]['id']))
        self.assertFalse(self.post('state', identity)['tutorial'])

    def test_practice_guidance_survives_alias_collisions_and_is_never_in_real_cases(self):
        for alias, field in (('Mara', 'question_target'), ('Ellis', 'suspect_target')):
            identity = self.post('tutorial', dict(name=alias, include_state=True))
            state = identity['state']
            target = state['scenario']['tutorial_guidance'][field]
            witness = next(actor for actor in state['scenario']['cast'] if actor['id'] == target)
            self.assertEqual(witness['name'], alias + ' Vale')
            self.post('solo-next', dict(identity, scenario_id=solo_story.SCENARIOS[0]['id']))
            real_case = self.post('state', identity)
            self.assertNotIn('tutorial_guidance', real_case['scenario'])

    def test_guided_tutorial_can_finish_in_one_round_using_normal_action_routes(self):
        identity = self.post('tutorial', dict(name='Learner'))
        room = game.rooms[identity['code']]
        self.post('start', identity)
        self.post('solo-proceed', identity)
        self.post('solo-proceed', identity)
        ids = solo_story.cast_ids(room)
        self.post('act', dict(identity, target=ids['ellis']))
        self.post('solo-proceed', identity)
        self.post('solo-question', dict(identity, target=ids['mara'], question='detail'))
        self.post('solo-evidence', dict(identity, action='inspect'))
        self.post('solo-evidence', dict(identity, action='compare'))
        state = self.post('state', identity)
        self.assertTrue(state['scenario']['interrogation']['used'])
        self.assertIn('dispatch-log', {entry['id'] for entry in state['scenario']['journal']})
        self.assertIn('dispatch-route', {entry['id'] for entry in state['scenario']['connections']})
        response = self.post('solo-influence', dict(identity, target=ids['ellis'], stance='suspect'))
        self.assertEqual(response['influence']['status'], 'accepted')
        self.assertTrue(response['influence']['changed_witnesses'])
        self.post('proceed', identity)
        self.post('vote', dict(identity, target=ids['ellis']))
        finished = self.post('state', identity)
        self.assertEqual((finished['phase'], finished['winner']), ('over', 'town'))
        self.assertTrue(all(player['score'] == 0 for player in finished['players']))


if __name__ == '__main__':
    unittest.main()
