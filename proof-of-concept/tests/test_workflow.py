import shutil
import tempfile
import unittest
from pathlib import Path

from poc.model import RulesPolicy
from poc.run import analyze


DEMO = Path(__file__).resolve().parents[1] / 'data' / 'demo'


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.case = Path(temporary.name) / 'case'
        shutil.copytree(DEMO, self.case)

    def run_case(self, policy=None):
        return analyze(self.case, policy or RulesPolicy())

    def test_recommendation_changes_after_reading_lab_evidence(self):
        run = self.run_case()
        hba1c, glucose = run['findings']
        self.assertEqual([hba1c['status'], glucose['status']], ['covered', 'gap_in_supplied_specs'])
        events = [event for event in run['trace'] if event['outcome'] == 'E1']
        first = next(i for i, event in enumerate(events) if event['event'] == 'initial_recommendation')
        lab = next(i for i, event in enumerate(events) if event.get('file') == 'lab_feed.csv')
        self.assertLess(first, lab)
        self.assertEqual([row['source']['line'] for row in events[lab]['matched_rows']], [2, 3])
        self.assertIn('Withdraw', hba1c['final'])
        self.assertEqual(glucose['missing_visits'], ['Week 24'])

    def test_unavailable_lab_spec_produces_unknown(self):
        (self.case / 'lab_feed.csv').unlink()
        self.assertEqual([finding['status'] for finding in self.run_case()['findings']], ['unknown', 'unknown'])

    def test_glucose_requires_both_the_visit_and_shared_participant_key(self):
        lab = self.case / 'lab_feed.csv'
        with lab.open('a', encoding='utf-8') as file:
            file.write('GLU_LOCAL,Fasting plasma glucose,Week 24,local_subject_id\n')
            file.write('GLU_WRONG_VISIT,Fasting plasma glucose,Week 12,participant_id\n')
        self.assertEqual(self.run_case()['findings'][1]['status'], 'gap_in_supplied_specs')
        with lab.open('a', encoding='utf-8') as file:
            file.write('GLU_W24,Fasting plasma glucose,W24,participant_id\n')
        self.assertEqual(self.run_case()['findings'][1]['status'], 'covered')

    def test_reviewer_can_request_lab_after_early_submission(self):
        class EarlySubmitPolicy(RulesPolicy):
            def choose(self, role, state, allowed):
                if role == 'investigator':
                    return {'action': 'submit', 'reason': 'Exercise the reviewer challenge path.'}
                return super().choose(role, state, allowed)

        run = self.run_case(EarlySubmitPolicy())
        verdicts = [event['action'] for event in run['trace']
                    if event['outcome'] == 'E1' and event['event'] == 'verdict']
        self.assertEqual(verdicts, ['request_lab', 'accept'])
        self.assertEqual(run['findings'][0]['status'], 'covered')

    def test_sap_disagreement_prevents_a_covered_finding(self):
        sap = self.case / 'sap.md'
        sap.write_text(sap.read_text(encoding='utf-8').replace('Baseline; Week 24', 'Baseline; Week 12'), encoding='utf-8')
        self.assertEqual(self.run_case()['findings'][0]['status'], 'unknown')
