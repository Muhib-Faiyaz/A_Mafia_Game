import json
import time
import unittest
from unittest.mock import patch
import app as game
import bot_brain


class SoloTeamTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.client = game.app.test_client()
        self.lead = self.post('solo', dict(name='Lead', include_state=True))
        self.room = game.rooms[self.lead['code']]
        self.invite = dict(code=self.lead['code'], invite=self.room['invite_token'])

    def post(self, route, body, status=200):
        response = self.client.post('/api/' + route, json=body)
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def join(self, name='Friend'):
        return self.post('solo-join', dict(self.invite, name=name, include_state=True))

    def test_invitation_required_and_two_friends_do_not_add_player_seats(self):
        self.post('solo-join', dict(code=self.lead['code'], name='Friend'), 404)
        for token in ['wrong', '\u2603', 123, None]:
            self.post('solo-join', dict(self.invite, name='Friend', invite=token), 404)
        self.post('join', dict(code=self.lead['code'], name='Friend'), 400)
        a, b = self.join('One'), self.join('Two')
        self.post('solo-join', dict(self.invite, name='Three'), 400)
        self.assertEqual(len(self.room['friends']), 2)
        self.assertEqual(len(self.room['players']), 7)
        self.assertNotIn(a['pid'], self.room['players'])
        self.assertNotIn(b['pid'], self.room['players'])
        self.post('start', self.lead)
        self.assertEqual(len(game.alive(self.room)), 7)
        self.assertEqual(len(game.alive(self.room, 'detective')), 1)
        self.assertEqual(len(game.alive(self.room, 'mafia')), 1)

    def test_aliases_are_distinct_from_cast_and_other_team_members(self):
        for name in ['lead', next(p['name'] for p in self.room['players'].values() if p['bot'])]:
            self.post('solo-join', dict(self.invite, name=name), 400)
        self.join('One')
        self.post('solo-join', dict(self.invite, name='oNe'), 400)

    def test_friend_view_and_host_controls(self):
        friend = self.join()
        state = friend['state']
        self.assertTrue(state['me']['friend'])
        self.assertFalse(state['me']['host'])
        self.assertEqual(state['me']['name'], 'Friend')
        self.assertIsNone(state['team']['invite_path'])
        self.assertEqual(len(state['team']['members']), 2)
        for route in ['start', 'restart', 'reset', 'end', 'bot', 'settings', 'tally', 'chat']:
            self.post(route, dict(friend, text='Public message'), 403)
        self.post('start', self.lead)
        state = self.post('state', friend)
        self.assertEqual(state['me']['role'], 'detective')
        self.assertEqual(next(p for p in state['players'] if p['you'])['id'], self.lead['pid'])
        self.assertIsNone(state['chat_mode'])

    def test_late_join_reload_leave_and_replay(self):
        self.post('start', self.lead)
        a, b = self.join('One'), self.join('Two')
        self.assertEqual(self.post('state', a)['team']['count'], 2)
        self.post('leave', a)
        self.post('state', a, 404)
        c = self.join('Replacement')
        self.assertIn(c['pid'], self.room['friends'])
        self.post('end', self.lead)
        self.post('restart', self.lead)
        self.assertEqual(self.post('state', b)['team']['count'], 2)
        self.post('leave', self.lead)
        self.post('state', b, 404)
        self.post('solo-join', dict(self.invite, name='Expired'), 404)

    def test_private_chat_is_not_exposed_to_bots_public_chat_or_their_beliefs(self):
        a, b = self.join('One'), self.join('Two')
        marker = 'private evidence for teammates only'
        for identity in [self.lead, a, b]:
            self.post('team-chat', dict(identity, text=marker, include_state=True))
        for identity in [self.lead, a, b]:
            state = self.post('state', identity)
            self.assertEqual(sum(m['t'] == marker for m in state['team_chat']), 3)
            self.assertNotIn(marker, json.dumps(state['chat']))
        npc = next(pid for pid, p in self.room['players'].items() if p['bot'])
        outsider = self.post('state', dict(code=self.lead['code'], pid=npc))
        self.assertIsNone(outsider['team'])
        self.assertEqual(outsider['team_chat'], [])
        self.assertNotIn(self.invite['invite'], json.dumps(outsider))
        self.assertNotIn(marker, repr(game.bot_context(self.room, npc)))
        self.post('team-chat', dict(code=self.lead['code'], pid=npc, text='Intruder'), 403)
        self.post('start', self.lead)
        self.room['friends'][a['pid']]['team_last'] = 0
        self.post('team-chat', dict(a, text='Even at night'))
        self.post('end', self.lead)
        self.room['friends'][a['pid']]['team_last'] = 0
        self.post('team-chat', dict(a, text='Even after the case'))

    def test_chat_is_bounded_and_throttled_per_author(self):
        a = self.join()
        self.post('team-chat', dict(a, text=' '), 400)
        self.post('team-chat', dict(a, text='x' * 600))
        self.assertEqual(len(self.room['team_chat'][-1]['t']), 500)
        self.post('team-chat', dict(a, text='Too soon'), 400)
        self.post('team-chat', dict(self.lead, text='Lead has a separate chat limit'))
        for i in range(110):
            game.team_message(self.room, 'Lead', str(i))
        self.assertEqual(len(self.room['team_chat']), 100)
        self.assertEqual(self.room['team_chat'][-1]['t'], '109')

    def test_investigation_is_one_shared_final_result_and_one_scoring_record(self):
        a, b = self.join('One'), self.join('Two')
        self.post('start', self.lead)
        target = game.alive(self.room, 'mafia')[0]
        self.post('act', dict(a, target=target))
        results = [self.post('state', identity)['investigation'] for identity in [self.lead, a, b]]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertTrue(results[0]['correct'])
        self.assertEqual(self.room['players'][self.lead['pid']]['investigated'], {target})
        self.post('act', dict(b, target=target), 400)
        self.assertEqual(len(self.room['players'][self.lead['pid']]['notes']), 1)
        npc = next(pid for pid, p in self.room['players'].items() if p['bot'] and p['role'] == 'town')
        self.assertIsNone(game.view(self.room, npc)['investigation'])
        self.room.update(phase='over', winner='town')
        game.settle_scores(self.room)
        self.assertEqual(self.room['players'][self.lead['pid']]['round_points'], 2)
        self.assertNotIn('score', self.room['friends'][a['pid']])

    def test_shared_readiness_counts_the_detective_seat_once(self):
        a, b = self.join('One'), self.join('Two')
        self.post('start', self.lead)
        self.room.update(phase='day', discuss_until=time.time() + 1000)
        with patch.object(game, 'run_bots'):
            for identity in [a, b, self.lead]:
                self.post('proceed', identity)
            state = self.post('state', b)
            self.assertEqual(state['discussion'], dict(ready=1, total=7, voted=True))
            self.assertEqual(self.room['discussion_ready'], {self.lead['pid']})
            for pid in game.alive(self.room):
                game.proceed_to_vote(self.room, pid)
            self.assertTrue(game.view(self.room, a['pid'])['voting'])

    def test_ballots_replace_one_shared_vote_and_never_add_friend_votes(self):
        a, b = self.join('One'), self.join('Two')
        self.post('start', self.lead)
        self.room.update(phase='day', discuss_until=0, votes={})
        targets = [pid for pid in self.room['players'] if pid != self.lead['pid']]
        with patch.object(game, 'run_bots'):
            self.post('vote', dict(a, target=targets[0]))
            self.post('vote', dict(b, target=targets[1]))
            self.post('vote', dict(self.lead, target='skip'))
            self.assertEqual(self.room['votes'], {self.lead['pid']: 'skip'})
            state = self.post('state', b)
            self.assertEqual(state['votes_left'], 6)
            self.assertEqual(state['skips'], 1)
            self.assertEqual(state['pick'], 'skip')
            for pid in targets:
                game.cast_vote(self.room, pid, 'skip')
            self.assertEqual(self.room['phase'], 'night')

    def test_protection_covers_bots_votes_and_defensive_night_resolution(self):
        self.post('start', self.lead)
        lead = self.lead['pid']
        for cause in ['night', 'vote']:
            game.record_death(self.room, lead, cause)
        self.assertTrue(self.room['players'][lead]['alive'])
        self.assertEqual(self.room['death_events'], [])
        self.room['night'].update(victim=lead, doctor=lead, resolved=False)
        game.resolve_night(self.room)
        self.assertEqual(self.room['dawn'], 'Nobody was killed last night.')
        self.assertEqual(self.room['death_events'], [])
        self.assertEqual(sum(p['pending_points'] for p in self.room['players'].values() if p['role'] == 'doctor'), 0)
        self.room.update(phase='day', discuss_until=0)
        for pid in game.alive(self.room):
            if pid == lead:
                continue
            with self.assertRaises(game.Bad):
                game.cast_vote(self.room, pid, lead)
            context = game.bot_context(self.room, pid)
            brain = bot_brain.new_brain()
            brain['checks'][lead] = True
            self.assertNotEqual(bot_brain.choose_target(brain, context), lead)
        self.room['votes'] = {pid: lead for pid in game.alive(self.room)}
        game.tally(self.room)
        self.assertTrue(self.room['players'][lead]['alive'])
        self.assertFalse(any('Lead was voted out' in x['t'] for x in self.room['log']))

    def test_mafia_can_still_win_without_killing_the_detective(self):
        self.join('One')
        self.join('Two')
        self.post('start', self.lead)
        innocents = [pid for pid in game.alive(self.room) if pid != self.lead['pid'] and self.room['players'][pid]['role'] != 'mafia']
        for pid in innocents:
            game.record_death(self.room, pid, 'vote')
        self.assertTrue(game.check_win(self.room))
        self.assertEqual(self.room['winner'], 'mafia')
        self.assertTrue(self.room['players'][self.lead['pid']]['alive'])
        self.assertEqual(self.room['players'][self.lead['pid']]['round_points'], 0)

    def final_chance_night(self, mafia_count=1):
        self.post('start', self.lead)
        mafia = game.alive(self.room, 'mafia')
        for pid in mafia[mafia_count:]:
            game.record_death(self.room, pid, 'vote')
        town = [pid for pid in game.alive(self.room) if self.room['players'][pid]['role'] == 'town']
        excess = len(game.alive(self.room)) - 2 * mafia_count - 1
        for pid in town[:excess]:
            game.record_death(self.room, pid, 'vote')
        game.start_night(self.room)
        return game.alive(self.room, 'mafia')

    def choose_detective_as_victim(self, mafia):
        for pid in mafia:
            game.mafia_vote(self.room, pid, self.lead['pid'])
        game.advance(self.room)
        self.assertEqual(self.room['night']['victim'], self.lead['pid'])
        # Deliberately protect somebody else; this test is about Detective findings.
        self.room['night']['doctor'] = mafia[0]
        game.advance(self.room)
        self.assertEqual(self.room['night_step'], 'detective')

    def test_final_night_wrong_investigation_can_kill_the_shared_detective(self):
        friend = self.join()
        mafia = self.final_chance_night()
        self.assertTrue(game.view(self.room, friend['pid'])['me']['at_risk'])
        self.choose_detective_as_victim(mafia)
        innocent = game.alive(self.room, 'doctor')[0]
        self.post('act', dict(friend, target=innocent))
        state = self.post('state', friend)
        self.assertFalse(state['me']['alive'])
        self.assertFalse(state['investigation']['correct'])
        self.assertEqual(state['winner'], 'mafia')
        self.assertEqual(state['phase'], 'over')
        lead = self.room['players'][self.lead['pid']]
        self.assertEqual(lead['round_points'], 0)
        self.assertEqual(sum(e['player_id'] == self.lead['pid'] for e in state['death_events']), 1)
        self.assertIn('Lead was killed', self.room['dawn'])

    def test_final_night_correct_investigation_stops_an_already_selected_attack(self):
        friend = self.join()
        mafia = self.final_chance_night()
        self.choose_detective_as_victim(mafia)
        self.post('act', dict(friend, target=mafia[0]))
        state = self.post('state', self.lead)
        self.assertTrue(state['me']['alive'])
        self.assertTrue(state['investigation']['correct'])
        self.assertFalse(state['me']['at_risk'])
        self.assertEqual(state['phase'], 'day')
        self.assertEqual(self.room['dawn'], 'Nobody was killed last night.')
        self.assertEqual(self.room['players'][game.alive(self.room, 'doctor')[0]]['pending_points'], 0)

    def test_final_night_timeout_without_a_finding_can_also_be_fatal(self):
        mafia = self.final_chance_night(mafia_count=1)
        self.choose_detective_as_victim(mafia)
        self.room['step_until'] = time.time() - 1
        game.advance(self.room)
        self.assertEqual(self.room['winner'], 'mafia')
        self.assertFalse(self.room['players'][self.lead['pid']]['alive'])

    def test_prior_surviving_finding_protects_but_stale_finding_does_not(self):
        mafia = self.final_chance_night(mafia_count=1)
        lead = self.lead['pid']
        eliminated = next(pid for pid, p in self.room['players'].items() if not p['alive'])
        self.room['players'][lead]['investigated'].add(eliminated)
        self.assertFalse(game.night_protected_player(self.room, lead))
        self.room['players'][lead]['investigated'].add(mafia[0])
        self.assertTrue(game.night_protected_player(self.room, lead))
        self.assertFalse(game.view(self.room, lead)['me']['at_risk'])
        with self.assertRaises(game.Bad):
            game.mafia_vote(self.room, mafia[0], lead)

    def test_doctor_can_save_the_detective_on_a_final_chance_night(self):
        mafia = self.final_chance_night()
        self.choose_detective_as_victim(mafia)
        self.room['night']['doctor'] = self.lead['pid']
        game.resolve_night(self.room)
        self.assertTrue(self.room['players'][self.lead['pid']]['alive'])
        self.assertEqual(self.room['phase'], 'day')
        self.assertIn('was saved by the Doctor', self.room['dawn'])
        self.assertEqual(self.room['players'][game.alive(self.room, 'doctor')[0]]['pending_points'], 1)

    def test_bot_mafia_can_choose_the_unprotected_detective_on_the_final_night(self):
        self.final_chance_night()
        lead = self.lead['pid']
        def pick_detective(choices):
            return lead if lead in choices else choices[0]
        with patch.object(game.random, 'choice', side_effect=pick_detective):
            game.run_bots(self.room)
        self.assertEqual(self.room['night']['victim'], lead)
        self.assertEqual(self.room['night_step'], 'detective')
        # Daytime voting protection stays in place even after a dangerous night.
        self.room.update(phase='day', discuss_until=0)
        with self.assertRaises(game.Bad):
            game.cast_vote(self.room, game.alive(self.room, 'mafia')[0], lead)
        self.assertFalse(game.view(self.room, lead)['me']['at_risk'])

    def test_online_game_has_no_solo_team_or_immunity(self):
        identity = self.post('create', dict(name='Host', include_state=True))
        room = game.rooms[identity['code']]
        self.post('bot', dict(identity, count=3))
        self.post('start', identity)
        self.assertIsNone(self.post('state', identity)['team'])
        self.post('team-chat', dict(identity, text='Private'), 403)
        self.post('solo-join', dict(code=identity['code'], name='Intruder', invite=self.invite['invite']), 404)
        game.record_death(room, identity['pid'], 'night')
        self.assertFalse(room['players'][identity['pid']]['alive'])
