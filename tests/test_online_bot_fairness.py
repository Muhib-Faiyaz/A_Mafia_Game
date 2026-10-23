"""Online bots must not turn repeated tentative gossip into a shared fact."""
import copy
import unittest
import bot_brain


class OnlineBotFairnessTests(unittest.TestCase):
    def setUp(self):
        self.players = [dict(id='human', name='Player', bot=False, alive=True)] + [
            dict(id=f'bot{i}', name=f'Bot {i}', bot=True, alive=True) for i in range(8)]

    def context(self, pid='bot0'):
        return dict(self=pid, players=copy.deepcopy(self.players), allies=set(), votes={})

    def hear(self, brain, context, author, text):
        bot_brain.hear(brain, dict(speaker=author, t=text, seq=1), context)

    def test_generated_hunches_do_not_snowball_onto_the_only_human(self):
        contexts = {p['id']: self.context(p['id']) for p in self.players if p['bot']}
        brains = {pid: bot_brain.new_brain() for pid in contexts}
        for i, (pid, brain) in enumerate(brains.items()):
            brain['focus'] = f'bot{(i + 1) % 8}'
        # One participant opens with a hunch about the human. It can be heard
        # and discussed, but every repetition remains the same unsupported hunch.
        initial = bot_brain.reply(dict(bot_brain.new_brain(), focus='human'), contexts['bot0'])
        self.assertIn('Player', initial)
        for pid, brain in brains.items():
            self.hear(brain, contexts[pid], 'bot0', initial)
        for _ in range(5):
            speeches = [(pid, bot_brain.reply(brain, contexts[pid])) for pid, brain in brains.items()]
            for target, brain in brains.items():
                for speaker, text in speeches:
                    self.hear(brain, contexts[target], speaker, text)
        for i, (pid, brain) in enumerate(brains.items()):
            self.assertEqual(bot_brain.scores(brain, contexts[pid])['human'], 0)
            self.assertEqual(bot_brain.choose_target(brain, contexts[pid]), f'bot{(i + 1) % 8}')

    def test_bot_assertions_are_capped_instead_of_counting_echoes_as_corroboration(self):
        context, brain = self.context(), bot_brain.new_brain()
        brain['focus'] = 'bot7'
        self.hear(brain, context, 'bot1', 'I suspect Player')
        single = bot_brain.scores(brain, context)['human']
        self.assertGreater(single, 0)
        for i in range(2, 8):
            self.hear(brain, context, f'bot{i}', 'I suspect Player')
        self.assertEqual(bot_brain.scores(brain, context)['human'], single)
        self.hear(brain, context, 'human', 'I suspect Bot 6')
        self.assertEqual(bot_brain.choose_target(brain, context), 'bot6')

    def test_claim_basis_changes_when_a_speaker_changes_certainty(self):
        context, brain = self.context(), bot_brain.new_brain()
        self.hear(brain, context, 'bot1', 'I lean towards Player; that is only a hunch.')
        self.assertEqual(bot_brain.scores(brain, context)['human'], 0)
        self.hear(brain, context, 'bot1', 'I suspect Player')
        self.assertGreater(bot_brain.scores(brain, context)['human'], 0)
        self.hear(brain, context, 'bot1', 'I lean towards Player for now.')
        self.assertEqual(bot_brain.scores(brain, context)['human'], 0)

    def test_role_labels_and_human_identity_do_not_establish_guilt(self):
        context, brain = self.context(), bot_brain.new_brain()
        brain['focus'] = 'bot5'
        expected = bot_brain.choose_target(brain, context)
        for player in context['players']:
            player['role'] = 'mafia' if player['id'] == 'human' else 'town'
        self.assertEqual(bot_brain.choose_target(brain, context), expected)
        self.assertEqual(bot_brain.scores(brain, context)['human'], 0)

    def test_private_investigation_still_overrides_gossip_and_player_arguments(self):
        context, brain = self.context(), bot_brain.new_brain()
        brain['checks'].update(human=False, bot4=True)
        self.hear(brain, context, 'bot1', 'I suspect Player')
        self.hear(brain, context, 'human', 'I trust Bot 4')
        self.assertEqual(bot_brain.choose_target(brain, context), 'bot4')
        brain['checks']['bot4'] = False
        self.assertNotIn(bot_brain.choose_target(brain, context), ['human', 'bot4'])

    def test_fallback_is_stable_for_one_bot_and_diverse_across_bots(self):
        choices = []
        for i in range(8):
            context, brain = self.context(f'bot{i}'), bot_brain.new_brain()
            brain['focus'] = 'departed-player'
            chosen = bot_brain.choose_target(brain, context)
            self.assertEqual(chosen, bot_brain.choose_target(brain, context))
            context['players'].reverse()
            self.assertEqual(chosen, bot_brain.choose_target(brain, context))
            choices.append(chosen)
        self.assertGreater(len(set(choices)), 2)

    def test_question_explanation_does_not_treat_a_repeated_hunch_as_evidence(self):
        context, brain = self.context(), bot_brain.new_brain()
        brain['focus'] = 'human'
        self.hear(brain, context, 'bot1', 'I lean towards Player; that is only a hunch.')
        pending = dict(message=dict(speaker='human'), intent=dict(question=True, stances={}))
        reply = bot_brain.reply(brain, context, pending)
        self.assertIn('my own read', reply)
        self.assertNotIn('concerns raised', reply)


if __name__ == '__main__':
    unittest.main()
