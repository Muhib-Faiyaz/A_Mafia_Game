import copy
import json
from pathlib import Path
import unittest

import case_details
import solo_story


ROOT = Path(__file__).resolve().parents[1]
PRACTICE = json.loads((ROOT / 'data/tutorial_case.json').read_text())


def room_for(case):
    case = copy.deepcopy(case)
    players = {'lead': dict(name='Reader', alive=True, role='detective')}
    for actor in case['cast']:
        role = 'mafia' if actor['key'] == case['culprit'] else 'doctor' if actor['key'] == case['doctor'] else 'town'
        players[actor['key']] = dict(name=actor['name'], alive=True, role=role, character=actor)
    room = dict(scenario=case, players=players, day=1, phase='day', solo_voting=False)
    solo_story.initialize(room)
    return room


class CaseDetailsTests(unittest.TestCase):
    def test_seven_public_cases_and_separate_practice_validate(self):
        self.assertEqual(len(solo_story.SCENARIOS), 7)
        self.assertNotIn(PRACTICE['id'], {case['id'] for case in solo_story.SCENARIOS})
        for case in (*solo_story.SCENARIOS, PRACTICE):
            with self.subTest(case=case['id']):
                self.assertEqual(case_details.validate_case(case), [])
                self.assertEqual(case['complexity'], case_details.complexity(case))

    def test_ratings_are_measured_and_not_forced_to_fill_the_scale(self):
        expected = {'ninth-photograph': 4, 'room-kept-warm': 3, 'carriage-six': 3,
                    'river-returned': 4, 'last-rehearsal': 4, 'winter-seed': 4,
                    'quiet-sentence': 5, 'practice-dispatch': 1}
        for case in (*solo_story.SCENARIOS, PRACTICE):
            self.assertEqual(case_details.complexity(case)['stars'], expected[case['id']])

    def test_five_thresholds_follow_evidence_demands(self):
        def measured(chain, timing, interpretation, false_leads):
            ids = ['item-' + str(index) for index in range(chain)]
            check = dict(requires=ids[:2], note='An independently reviewable reasoning demand.')
            case = dict(clues=[dict(id=key, source=key) for key in ids],
                        connections=[dict(requires=ids, effect=2.2)]
                        + [dict(requires=ids[:2], effect=-1.8) for _ in range(false_leads)],
                        reasoning=dict(timing=[check] * timing, interpretation=[check] * interpretation))
            return case_details.complexity(case)['stars']
        self.assertEqual(measured(2, 0, 0, 0), 1)
        self.assertEqual(measured(2, 2, 1, 0), 2)
        self.assertEqual(measured(2, 2, 2, 1), 3)
        self.assertEqual(measured(3, 2, 2, 1), 4)
        self.assertEqual(measured(4, 2, 2, 1), 5)

    def test_public_rating_recomputes_stale_metadata_and_drops_private_extras(self):
        case = copy.deepcopy(solo_story.SCENARIOS[0])
        expected = case_details.complexity(case)
        case['complexity'] = dict(stars=True, label=case['solution'], reason=case['solution'],
                                  factors=dict(culprit=case['culprit']), culprit=case['culprit'])
        actual = case_details.complexity(case)
        self.assertEqual(actual, expected)
        self.assertEqual(set(actual), {'stars', 'label', 'reason', 'factors'})
        self.assertEqual(set(actual['factors']), set(case_details.FACTOR_KEYS))
        self.assertTrue(all(type(value) is int for value in actual['factors'].values()))
        self.assertTrue(any('Stored complexity' in error for error in case_details.validate_case(case)))
        actual['factors']['timing_checks'] = 99
        self.assertEqual(case_details.complexity(case), expected)

    def test_invalid_reasoning_and_unknown_hint_sources_are_reported(self):
        case = copy.deepcopy(solo_story.SCENARIOS[0])
        case['reasoning']['timing'][0]['requires'] = ['not-a-clue', 'also-not-a-clue']
        case['incidents']['leads'][0]['requires'] = ['not-a-clue']
        errors = case_details.validate_case(case)
        self.assertTrue(any('timing' in error for error in errors))
        self.assertTrue(any('Incident leads' in error for error in errors))

    def test_incidents_are_local_and_do_not_publish_unknown_facts_or_roles(self):
        for case in solo_story.SCENARIOS:
            room = room_for(case)
            with self.subTest(case=case['id']):
                before = copy.deepcopy(room)
                for cause in ('night', 'vote', 'rescue'):
                    text = (case_details.rescue_story(room, 'Reader') if cause == 'rescue'
                            else case_details.death_story(room, 'Reader', cause))
                    self.assertEqual(text, case['incidents'][cause].replace('{name}', 'Reader'))
                    self.assertIn('Reader', text)
                    for actor in case['cast']:
                        self.assertNotIn(actor['name'], text)
                    self.assertNotIn(case['solution'], text)
                self.assertEqual(room, before)

    def test_quiet_leads_require_every_source_and_a_completed_public_stage(self):
        for case in solo_story.SCENARIOS:
            room = room_for(case)
            lead = case['incidents']['leads'][0]
            base = case_details.death_story(room, 'Reader', 'night')
            with self.subTest(case=case['id']):
                for missing in lead['requires']:
                    room['story']['revealed'] = {key: {} for key in lead['requires'] if key != missing}
                    self.assertEqual(case_details.death_story(room, 'Reader', 'night'), base)
                room['story']['revealed'] = {key: {} for key in lead['requires']}
                room['day'] = 0
                self.assertEqual(case_details.death_story(room, 'Reader', 'night'), base)
                room['day'] = 1
                before = copy.deepcopy(room['story'])
                self.assertEqual(case_details.death_story(room, 'Reader', 'night'), base + ' ' + lead['text'])
                self.assertEqual(room['story'], before)
                self.assertNotIn(lead['text'], case_details.rescue_story(room, 'Reader'))
                self.assertNotIn(lead['text'], case_details.death_story(room, 'Reader', 'vote'))

    def test_incident_fallback_never_formats_unknown_fields(self):
        room = dict(scenario=dict(incidents=dict(night='{name} saw {culprit}.', leads=[])))
        self.assertIn('Reader does not return', case_details.death_story(room, 'Reader', 'night'))
        self.assertNotIn('culprit', case_details.death_story(room, 'Reader', 'night'))
        self.assertIn('Reader survives', case_details.rescue_story({}, 'Reader'))

    def test_practice_question_and_document_support_a_one_round_ballot(self):
        room, messages = room_for(PRACTICE), []
        publish = lambda *parts: messages.append(parts)
        solo_story.discussion(room, publish)
        self.assertIn('theo-observation', room['story']['revealed'])
        self.assertNotIn('mara-observation', room['story']['revealed'])
        self.assertEqual(room['story']['connections'], {})
        self.assertTrue(next(option for option in solo_story.question_options(room, 'mara')
                             if option['id'] == 'detail')['available'])
        solo_story.ask_question(room, 'mara', 'detail', publish)
        self.assertEqual(room['story']['connections'], {})
        solo_story.evidence(room, 'inspect', publish)
        self.assertIn('dispatch-log', room['story']['revealed'])
        self.assertNotIn('shelf-photo', room['story']['revealed'])
        self.assertEqual(set(room['story']['connections']), {'dispatch-route'})
        self.assertEqual(solo_story.vote_target(room, 'priya'), 'skip')
        solo_story.influence(room, 'lead', 'ellis', 'suspect', publish)
        for pid, player in room['players'].items():
            if player['role'] in ('town', 'doctor'):
                self.assertEqual(solo_story.vote_target(room, pid), 'ellis')

    def test_private_wording_is_not_opened_by_a_chapter_before_inspection(self):
        case = next(case for case in solo_story.SCENARIOS if case['id'] == 'quiet-sentence')
        room = room_for(case)
        solo_story.discussion(room, lambda *args: None)
        self.assertNotIn('corrected-page', room['story']['revealed'])
        self.assertIn('remains sealed until inspection', room['story']['chapters'][0]['text'])


if __name__ == '__main__':
    unittest.main()
