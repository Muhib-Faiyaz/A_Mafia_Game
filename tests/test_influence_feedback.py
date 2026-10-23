import copy
import unittest

import app as game
import solo_story


class InfluenceFeedbackTests(unittest.TestCase):
    def setUp(self):
        game.rooms.clear()
        self.client = game.app.test_client()
        self.identity = self.post('solo', {'name': 'Reader', 'scenario_id': solo_story.SCENARIOS[0]['id']})
        self.room = game.rooms[self.identity['code']]
        self.post('start')
        self.post('solo-proceed')
        self.post('solo-proceed')
        self.room['night']['victim'] = None
        self.post('solo-proceed')
        self.link = next(link for link in self.room['scenario']['connections'] if link['effect'] > 0)
        self.target = solo_story.cast_ids(self.room)[self.link['subject']]

    def post(self, route, body=None, status=200):
        response = self.client.post('/api/' + route, json=dict(getattr(self, 'identity', {}), **(body or {})))
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def test_unsupported_claim_is_accepted_without_pretending_it_changed_votes(self):
        feedback = self.post('solo-influence', {'target': self.target, 'stance': 'suspect'})['influence']
        self.assertEqual(feedback['status'], 'accepted')
        self.assertEqual(feedback['changed_witnesses'], [])
        self.assertEqual(feedback['before'], feedback['after'])
        self.assertIn('no witness changed', feedback['message'])
        self.assertEqual(self.post('state')['scenario']['influence_feedback'], feedback)

    def test_supported_claim_reports_exact_changes_and_repeat_does_not_stack(self):
        self.room['story']['connections'][self.link['id']] = {'id': self.link['id']}
        feedback = self.post('solo-influence', {'target': self.target, 'stance': 'suspect'})['influence']
        actual = [new['name'] for old, new in zip(feedback['before'], feedback['after']) if old['target'] != new['target']]
        self.assertTrue(actual)
        self.assertEqual(feedback['changed_witnesses'], actual)
        for entry in feedback['after']:
            pid = next(pid for pid, p in self.room['players'].items() if p['name'] == entry['name'])
            self.assertEqual(entry['target'], solo_story.vote_target(self.room, pid))
        claims = copy.deepcopy(self.room['story']['claims'])
        repeated = self.post('solo-influence', {'target': self.target, 'stance': 'suspect'})['influence']
        self.assertEqual(repeated['status'], 'unchanged')
        self.assertEqual(repeated['changed_witnesses'], [])
        self.assertEqual(claims, self.room['story']['claims'])
        defended = self.post('solo-influence', {'target': self.target, 'stance': 'defend'})['influence']
        self.assertTrue(defended['changed_witnesses'])

    def test_rejected_actions_cannot_change_claims_or_replace_success_feedback(self):
        self.post('solo-influence', {'target': self.target, 'stance': 'suspect'})
        before = copy.deepcopy(self.room['story'])
        for body in ({'target': 'missing', 'stance': 'suspect'}, {'target': self.target, 'stance': 'wrong'}):
            self.post('solo-influence', body, 400)
            self.assertEqual(before, self.room['story'])
        self.post('proceed')
        self.post('solo-influence', {'target': self.target, 'stance': 'defend'}, 400)
        self.assertEqual(before['claims'], self.room['story']['claims'])

    def test_private_detective_result_does_not_persuade_witnesses(self):
        self.room['players'][self.identity['pid']]['found_mafia'] = True
        feedback = self.post('solo-influence', {'target': self.target, 'stance': 'suspect'})['influence']
        self.assertEqual(feedback['changed_witnesses'], [])


if __name__ == '__main__':
    unittest.main()
