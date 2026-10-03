"""Synthetic local control example. --live uses the owner's Codex subscription.

No hardware, purchase, formal adoption or publisher-funded API is involved.
The default deterministic review/developer responses are explicitly fixtures.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

from gantry.project_connect import connect, Project, owner_client
from gantry.project_mcp import dispatch
from gantry.monthly_codex import infer_monthly
from gantry.model import require


def demonstration(root, live=False):
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=False)
    (root/'control.py').write_text('def clamp(x):\n    return min(x, 10)\n')
    (root/'tests').mkdir()
    (root/'tests/test_control.py').write_text('import unittest\nfrom control import clamp\nclass Check(unittest.TestCase):\n'
        '    def test_range(self):\n        self.assertEqual(clamp(-1), 0)\n        self.assertEqual(clamp(20), 10)\n        self.assertEqual(clamp(3), 3)\n')
    delegation = {'goal': 'Clamp a simulated actuator request to [0, 10]',
        'done': ['Negative requests return zero, requests above ten return ten, and three returns three'],
        'constraints': ['Only change control.py; do not edit the acceptance tests or operate hardware'],
        'hold': ['Stop if the saved bounds must change'], 'max_reviews': None, 'max_tests': None, 'max_branches': 2,
        'mentor': 'codex-subscription' if live else 'client'}
    # Harness stands in for the owner's one approval of this synthetic fixture only.
    connection = connect(root, write_paths=['control.py'], commands={'test': {'argv': [str(Path(sys.executable).resolve()), '-B', '-m',
        'unittest', 'discover', '-s', 'tests'], 'timeout_seconds': 15}}, delegation=delegation, confirm=lambda _: True)
    project = Project(root)
    failed = project.operate('test', {'command': 'test'}, 'baseline-test')
    require(failed['exit_code'] != 0, 'demo_failed', 'Fixture should fail before correction')
    state = project.context()['connection']['state_id']
    saved = project.operate('checkpoint', {'expected_state': state, 'summary': 'Observed lower-bound failure',
        'rationale': 'Submit a meaningful failed milestone for review', 'unfinished': ['Correct the clamp']}, 'save-failure')
    submitted = project.operate('submit', {'question': 'Inspect control.py and the failed test; propose a concrete correction'}, 'submit-failure')
    submission = submitted['submission'] if live else submitted
    if live:
        review = submitted['review']['review']; provider = submitted['review']['provider']
    else:
        dispatch(project, 'project_mentor_prepare', {'submission_id': submission['id']})
        state = saved['state']['id']
        review = dispatch(project, 'project_mentor_finish', {'submission_id': submission['id'], 'output': {
            'verdict': 'changes_requested', 'scope': 'Simulated request bounds', 'rationale': 'The saved negative-input test fails',
            'evidence': [state], 'unverified': ['Physical performance'], 'prediction': 'Adding a lower bound should satisfy the tests',
            'findings': [{'id': 'lower-bound', 'summary': 'Missing lower bound', 'paths': ['control.py'],
                'evidence': [state], 'proposed_change': 'return max(0, min(x, 10))', 'completion_condition': 'Run the fixed acceptance tests'}]}})
        provider = {'kind': 'deterministic_fixture'}
    require(review['output']['findings'], 'demo_failed', 'Expected an actionable review')
    if live:
        schema = {'type': 'object', 'properties': {'content': {'type': 'string'}, 'reason': {'type': 'string'}},
                  'required': ['content', 'reason'], 'additionalProperties': False}
        proposal = infer_monthly({'task': 'Return the complete corrected control.py, using only the saved Mentor findings.',
            'current_file': (root/'control.py').read_text(), 'review': review['output'], 'constraints': delegation['constraints']},
            schema, root/'.gantry/developer-inference')
        content = proposal['output']['content']; developer_provider = proposal['provider']
    else:
        content = 'def clamp(x):\n    return max(0, min(x, 10))\n'; developer_provider = {'kind': 'deterministic_fixture'}
    old = project.operate('read', {'path': 'control.py'}, 'read-correction')
    project.operate('edit', {'path': 'control.py', 'expected_hash': old['sha256'], 'content': content,
        'from_review': submission['id']}, 'apply-correction')
    passed = project.operate('test', {'command': 'test'}, 'corrected-test')
    require(passed['exit_code'] == 0, 'demo_failed', 'Corrected candidate did not satisfy the same tests')
    corrected = project.operate('checkpoint', {'expected_state': saved['state']['id'], 'summary': 'Corrected clamp; tests pass',
        'rationale': 'Followed the saved Mentor findings', 'unfinished': ['Physical integration remains unverified']}, 'save-correction')
    project.operate('respond', {'submission_id': submission['id'], 'responses': [
        {'finding_id': f['id'], 'explanation': 'Corrected control.py; the unchanged test command now succeeds'}
        for f in review['output']['findings']]}, 'respond')
    resumed = Project(root).context()
    owner = owner_client(root/'.gantry')
    result = {'connected': connection['status'], 'initial_test_exit': failed['exit_code'], 'corrected_test_exit': passed['exit_code'],
        'saved_and_resumed': resumed['connection']['state_id'] == corrected['state']['id'],
        'adoption': resumed['development']['status']['adoption'], 'verification': resumed['development']['status']['verification'],
        'review_provider': provider, 'developer_provider': developer_provider,
        'sandbox': passed['sandbox'], 'audit_verified': owner.call('verify')['valid'], 'replay_matched': owner.call('replay')['matched'],
        'manual': ['Initial approval represented by fixture harness', 'Harness invokes the user-agent continuation'],
        'automatic': ['Core policy checks', 'Saved-file capture', 'Review leases and history', 'Sandbox execution', 'Result collection'],
        'mock': [] if live else ['Mentor findings', 'Developer correction'], 'hardware_operated': False}
    (root/'.gantry/demonstration.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='New private demonstration directory')
    parser.add_argument('--live', action='store_true', help='Two bounded Codex calls under your existing ChatGPT login; no API-key fallback')
    args = parser.parse_args()
    print(json.dumps(demonstration(args.output, args.live), indent=2))
