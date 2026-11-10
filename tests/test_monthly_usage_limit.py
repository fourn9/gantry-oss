"""Terminal subscription exhaustion is not a transient 429 or an uncertain tool effect."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gantry.model import Fault
from gantry.monthly_codex import infer_monthly
from gantry.monthly_recovery import prepare_retry, rate_limit_state

MESSAGE = "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at Jan 1st, 2099 7:26 PM."


def quota_journal(root, **changes):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    state = {'phase': 'started', 'pid': 99999999, 'context': {'task': 'sample'}, 'schema': {},
             'inference_settings': {'model': 'pinned'}, 'failures': 0}
    state.update(changes)
    (root/'inference.json').write_text(json.dumps(state))
    (root/'events.jsonl').write_text(json.dumps({'type': 'turn.failed', 'error': {'message': MESSAGE}})+'\n')
    return state


class MonthlyUsageLimitTests(unittest.TestCase):
    def test_actual_shaped_terminal_cli_error_is_specific_and_never_relaunched(self):
        launches=[]
        class Process:
            pid=99999999
            returncode=1
            def __init__(self, argv, **kw): launches.append(argv); self.events=kw['stdout']
            def communicate(self, prompt, timeout):
                self.events.write(json.dumps({'type':'turn.failed','error':{'message':MESSAGE}})+'\n')
                self.events.flush()
        with tempfile.TemporaryDirectory() as directory, patch('gantry.monthly_codex.subprocess.run', return_value=SimpleNamespace(returncode=0,stdout='ChatGPT',stderr='')), patch('gantry.monthly_codex.subprocess.Popen', Process):
            for _ in range(2):
                with self.assertRaises(Fault) as caught: infer_monthly({}, {}, directory)
                self.assertEqual(caught.exception.code, 'provider_usage_limited')
            self.assertEqual(len(launches), 1)
            saved=json.loads((Path(directory)/'inference.json').read_text())
            self.assertEqual(saved['code'], 'provider_usage_limited')
            self.assertNotIn('retry_at', saved)

    def test_explicit_retry_preserves_original_evidence_and_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); original=quota_journal(root)
            prepare_retry(root, 'Operator confirmed restored monthly allowance')
            armed=json.loads((root/'inference.json').read_text())
            self.assertEqual(armed['phase'], 'retry_ready')
            self.assertEqual(armed['context'], original['context'])
            self.assertEqual(armed['inference_settings'], original['inference_settings'])
            archives=list((root/'recoveries').glob('*/events.jsonl'))
            self.assertEqual(len(archives), 1)
            self.assertEqual(archives[0].read_text(), (root/'events.jsonl').read_text())

    def test_partial_answer_agent_text_and_completed_turn_do_not_classify_as_quota(self):
        for mode in ['answer','agent','completed','quoted','malformed']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);state=quota_journal(root)
                if mode=='answer': (root/'answer.json').write_text('{}')
                elif mode=='agent':
                    with (root/'events.jsonl').open('a') as f:f.write(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':MESSAGE}})+'\n')
                elif mode=='completed':
                    with (root/'events.jsonl').open('a') as f:f.write('{"type":"turn.completed"}\n')
                elif mode=='quoted': (root/'events.jsonl').write_text(json.dumps({'type':'turn.failed','error':{'message':'Unrelated error quoting: '+MESSAGE}}))
                else: (root/'events.jsonl').write_text('not json')
                self.assertIsNone(rate_limit_state(root,state))
                with self.assertRaises(Fault) as caught: prepare_retry(root, 'Do not discard uncertain output')
                self.assertEqual(caught.exception.code,'outcome_unknown')

    def test_cached_quota_receipt_does_not_discard_late_response_evidence(self):
        for mode in ['answer','agent','completed','missing_pid','live_pid']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);state=quota_journal(root)
                saved=rate_limit_state(root,state)
                self.assertEqual(saved['code'],'provider_usage_limited')
                if mode=='answer': (root/'answer.json').write_text('{}')
                elif mode in {'agent','completed'}:
                    event=({'type':'item.completed','item':{'type':'agent_message','text':'saved result'}} if mode=='agent' else {'type':'turn.completed'})
                    with (root/'events.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
                else:
                    saved['pid']=None if mode=='missing_pid' else os.getpid()
                    (root/'inference.json').write_text(json.dumps(saved))
                with self.assertRaises(Fault) as caught:prepare_retry(root,'Still requires evidence reconciliation')
                self.assertEqual(caught.exception.code,'outcome_unknown')
                self.assertFalse((root/'recoveries').exists())

    def test_live_process_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            quota_journal(directory,pid=os.getpid())
            with self.assertRaises(Fault) as caught:prepare_retry(directory,'Operator assertion alone is insufficient')
            self.assertEqual(caught.exception.code,'outcome_unknown')
