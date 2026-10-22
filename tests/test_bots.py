import time
import unittest
from unittest.mock import patch
import bot_brain
import app as game


class BotLanguageTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(self='bot', allies=set(), votes={}, players=[
            dict(id=pid, name=name, bot=pid.startswith('bot'), alive=True)
            for pid, name in [('host', 'Host'), ('alice', 'Alice'), ('bob', 'Bob'), ('bot', 'Bot 1'), ('bot10', 'Bot 10')]])
        self.brain = bot_brain.new_brain()
        self.brain['focus'] = 'bob'

    def hear(self, text, speaker='host'):
        bot_brain.hear(self.brain, dict(t=text, speaker=speaker, seq=1), self.context)

    def test_accusations_defenses_negations_and_exact_aliases(self):
        for text, expected in [('I suspect Alice', 2), ('vote for Alice', 2),
                               ('Alice is Mafia', 2), ("I don't trust Alice", 2),
                               ('I trust Alice', -2), ("don't vote Alice", -2),
                               ('Alice is not Mafia', -2), ('Alice is innocent', -2)]:
            with self.subTest(text=text):
                self.assertEqual(bot_brain.read_message(text, self.context['players'])['stances'], {'alice': expected})
        parsed = bot_brain.read_message('@Bot 10, I suspect Alice', self.context['players'])
        self.assertEqual(parsed['addressed'], 'bot10')
        self.assertNotIn('bot', parsed['mentions'])
        self.assertEqual(bot_brain.read_message('Why do you suspect Alice?', self.context['players'])['stances'], {})

    def test_claim_changes_a_choice_but_repetition_does_not_multiply_it(self):
        self.assertEqual(bot_brain.choose_target(self.brain, self.context), 'bob')
        self.hear('I suspect Alice')
        self.assertEqual(bot_brain.choose_target(self.brain, self.context), 'alice')
        score = bot_brain.scores(self.brain, self.context)['alice']
        for _ in range(20):
            self.hear('I suspect Alice')
        self.assertEqual(bot_brain.scores(self.brain, self.context)['alice'], score)
        self.hear('I trust Alice')
        self.assertEqual(bot_brain.choose_target(self.brain, self.context), 'bob')

    def test_bot_claims_influence_other_bots_and_own_checks_override_hearsay(self):
        self.hear('I suspect Alice', 'bot10')
        self.assertEqual(bot_brain.choose_target(self.brain, self.context), 'alice')
        self.brain['checks']['alice'] = False
        self.assertNotEqual(bot_brain.choose_target(self.brain, self.context), 'alice')
        self.brain['checks']['bob'] = True
        self.assertEqual(bot_brain.choose_target(self.brain, self.context), 'bob')
        self.assertNotIn('Detective', bot_brain.reply(self.brain, self.context))

    def test_changed_bot_opinion_replaces_its_previous_accusation(self):
        self.hear('I suspect Alice', 'bot10')
        self.hear('I suspect Bob', 'bot10')
        self.assertEqual(bot_brain.scores(self.brain, self.context)['alice'], 0)
        self.assertEqual(bot_brain.choose_target(self.brain, self.context), 'bob')

    def test_verified_false_claims_reduce_speaker_trust(self):
        self.brain['checks']['alice'] = False
        self.hear('I suspect Alice')
        self.hear('I suspect Bob')
        self.assertEqual(bot_brain.scores(self.brain, self.context)['bob'], 0.5)
        self.hear('I trust Alice')
        self.assertEqual(bot_brain.scores(self.brain, self.context)['bob'], 2.8)


class BotInteractionTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.client = game.app.test_client()
        self.host = self.post('create', {'name': 'Host'})
        self.humans = [self.host] + [self.post('join', {'code': self.host['code'], 'name': name}) for name in ['Alice', 'Bob', 'Carol']]
        self.post('bot', dict(self.host, count=2))
        self.post('start', self.host)
        self.room = game.rooms[self.host['code']]
        self.players = self.room['players']
        self.bots = [pid for pid, p in self.players.items() if p['bot']]
        for player in self.players.values():
            player.update(role='town', alive=True, brain=bot_brain.new_brain())
        self.players[self.humans[1]['pid']]['role'] = 'mafia'
        self.players[self.humans[3]['pid']]['role'] = 'doctor'
        self.players[self.bots[1]]['role'] = 'detective'
        self.room.update(phase='day', day=1, votes={}, discussion_ready=set(),
                         discuss_until=time.time() + 1000, chat=[], chat_seq=0, bot_last_spoke=time.time(), bot_human_replied=0)
        for pid in self.bots:
            self.players[pid]['brain'].update(day=1, opened=True, focus=self.humans[2]['pid'])

    def post(self, route, data):
        response = self.client.post('/api/' + route, json=data)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def chat(self, text, channel='town'):
        self.players[self.host['pid']]['last'] = 0
        return self.post('chat', dict(self.host, channel=channel, text=text, include_state=True))['state']

    def open_vote(self):
        for user in self.humans:
            self.post('proceed', user)
        self.assertFalse(game.discussing(self.room))

    def test_players_persuade_bots_and_change_actual_ballots(self):
        self.open_vote()
        self.assertTrue(all(self.room['votes'][pid] == self.humans[2]['pid'] for pid in self.bots))
        self.chat('I suspect Alice')
        self.assertTrue(all(self.room['votes'][pid] == self.humans[1]['pid'] for pid in self.bots))
        self.chat("Don't vote Alice. I suspect Carol")
        self.assertTrue(all(self.room['votes'][pid] == self.humans[3]['pid'] for pid in self.bots))
        state = self.post('state', self.host)
        self.assertTrue(any('changed their vote' in c['t'] for c in state['chat']))

    def test_addressed_bot_answers_question_and_defends_itself(self):
        state = self.chat('@Bot 1, why Bob?')
        answers = [c for c in state['chat'] if c['n'] == 'Bot 1']
        self.assertTrue(any('@Host' in c['t'] and 'because' in c['t'] for c in answers))
        state = self.chat('I suspect Bot 1')
        self.assertTrue(any(c['n'] == 'Bot 1' and 'disagree about me' in c['t'] for c in state['chat']))

    def test_bot_to_bot_dialogue_and_post_budget(self):
        self.chat('I suspect Alice')
        now = time.time()
        for step in range(1, 12):
            with patch.object(game.time, 'time', return_value=now + step * 5):
                self.post('state', self.host)
        messages = [c for c in self.room['chat'] if c['k'] == 'msg' and c['speaker'] in self.bots]
        self.assertTrue(any('@Bot ' in c['t'] for c in messages))
        for pid in self.bots:
            self.assertLessEqual(sum(c['speaker'] == pid for c in messages), bot_brain.MAX_POSTS)
        self.assertEqual(self.room['phase'], 'day')

    def test_private_chat_does_not_influence_town_bots(self):
        self.players[self.host['pid']]['role'] = 'mafia'
        self.chat('I suspect Alice', channel='mafia')
        for pid in self.bots:
            self.assertNotIn((self.host['pid'], self.humans[1]['pid']), self.players[pid]['brain']['claims'])

    def test_context_hides_roles_and_private_state(self):
        context = game.bot_context(self.room, self.bots[0])
        self.assertTrue(all(set(p) == {'id', 'name', 'alive', 'bot'} for p in context['players']))
        self.assertEqual(context['allies'], set())
        choice = bot_brain.choose_target(self.players[self.bots[0]]['brain'], context)
        self.players[self.humans[1]['pid']]['role'], self.players[self.humans[2]['pid']]['role'] = 'town', 'mafia'
        self.assertEqual(bot_brain.choose_target(self.players[self.bots[0]]['brain'], game.bot_context(self.room, self.bots[0])), choice)
        state = self.post('state', self.host)
        self.assertNotIn('brain', state)
        self.assertTrue(all('brain' not in p for p in state['players']))

    def test_mafia_bot_does_not_vote_for_known_partner(self):
        pid = self.bots[0]
        self.players[pid]['role'] = 'mafia'
        self.chat('I suspect Alice')
        self.assertNotEqual(bot_brain.choose_target(self.players[pid]['brain'], game.bot_context(self.room, pid)), self.humans[1]['pid'])

    def test_restart_clears_beliefs_and_private_checks(self):
        self.chat('I suspect Alice')
        self.players[self.bots[0]]['brain']['checks'][self.humans[1]['pid']] = True
        self.post('restart', self.host)
        brain = self.players[self.bots[0]]['brain']
        self.assertEqual(brain['claims'], {})
        self.assertEqual(brain['checks'], {})
