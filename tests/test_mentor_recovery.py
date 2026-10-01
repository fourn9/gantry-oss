import json
import os
import sys
import unittest
from unittest.mock import patch

import test_mentor_safety as fixture
from gantry import mentor_daemon
from gantry.mentor_daemon import process_job
from gantry.mentor_recovery import recover_job
from gantry.model import Fault, digest
from gantry.runner import persist


class RecoveryTests(fixture.MentorSafetyTests):
    def pause_verified(self):
        job = self.developer_job()
        recipe = {'argv': [sys.executable, '-c', 'open("input.txt","a").write("-once")'], 'timeout_seconds': 10}
        self.permit_verification(recipe)
        journal = self.root / 'recovery'
        with patch.object(mentor_daemon, 'capture_workspace', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                process_job(self.client, job['id'], journal, self.inference, verification=recipe)
        return job, recipe, journal

    def test_expired_verified_job_resumes_without_model_or_tool_repeat(self):
        job, recipe, journal = self.pause_verified()
        old = json.loads((journal / digest(job['id']) / 'job.json').read_text())
        now = self.service.clock(); self.service.clock = lambda: now + 901000
        recover_job(self.client, job['id'], journal, 'Previous worker exited, no child remains')
        self.fault('unauthorized', lambda: self.client.call('check_mentor_job',
            {'job_id': job['id'], 'fence': old['job']['fence']}))
        def forbidden(*args): self.fail('Completed inference repeated')
        with patch.object(mentor_daemon.subprocess, 'Popen', side_effect=AssertionError('Verifier repeated')):
            result = process_job(self.client, job['id'], journal, forbidden, verification=recipe)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual((journal / digest(job['id']) / 'workspace/input.txt').read_text(), 'corrected-once')
        self.assertEqual(self.detail()['session']['used_executions'], 1)
        self.assertTrue(self.call('replay')['matched'])

    def test_recovery_lost_ack_is_idempotent(self):
        job, recipe, journal = self.pause_verified()
        real = self.client
        class LostAck:
            def call(self, name, args=None, key=None):
                result = real.call(name, args, key)
                if name == 'recover_mentor_job': raise OSError('response lost')
                return result
        with self.assertRaises(OSError): recover_job(LostAck(), job['id'], journal, 'Worker stopped')
        self.fault('recovery_pending', lambda: process_job(real, job['id'], journal, self.inference, verification=recipe))
        recover_job(real, job['id'], journal, 'Worker stopped')
        row = next(x for x in self.jobs() if x['id'] == job['id'])
        self.assertEqual(len(row['recoveries']), 1)
        self.assertEqual(process_job(real, job['id'], journal, self.inference, verification=recipe)['status'], 'completed')

    def test_revoked_or_changed_candidate_cannot_recover(self):
        job, recipe, journal = self.pause_verified()
        self.checkpoint(self.cp['change'], {'input.txt': 'another candidate'})
        self.fault('stale_basis', lambda: recover_job(self.client, job['id'], journal, 'Stopped'))

    def test_provider_uncertainty_requires_explicit_retry_and_uses_new_directory(self):
        self.setup_jobs(); job = self.job('specialist'); journal = self.root / 'provider'
        directories = []
        def stopped(ctx, schema, directory):
            directories.append(str(directory))
            persist(directory / 'inference.json', {'phase': 'started', 'context': ctx, 'schema': schema})
            raise Fault('provider_timeout', 'Stopped provider')
        self.fault('provider_timeout', lambda: process_job(self.mentor, job['id'], journal, stopped))
        j = json.loads((journal / digest(job['id']) / 'job.json').read_text())
        self.mentor.call('fail_mentor_job', {'job_id': job['id'], 'fence': j['job']['fence'], 'reason': 'provider_timeout'})
        self.fault('outcome_unknown', lambda: recover_job(self.mentor, job['id'], journal, 'Process stopped'))
        used = self.call('review_automation_status', {'session_id': self.session['id']})['policy']['used_jobs']
        recover_job(self.mentor, job['id'], journal, 'Confirmed timeout termination', retry_inference=True)
        def complete(ctx, schema, directory):
            directories.append(str(directory)); return self.inference(ctx, schema, directory)
        process_job(self.mentor, job['id'], journal, complete)
        self.assertNotEqual(*directories)
        self.assertTrue((journal / digest(job['id']) / 'model/inference.json').exists())
        self.assertEqual(self.call('review_automation_status', {'session_id': self.session['id']})['policy']['used_jobs'], used + 1)

    def test_active_process_cannot_be_recovered(self):
        self.setup_jobs(); job = self.job('specialist'); journal = self.root / 'active'
        def active(ctx, schema, directory):
            persist(directory / 'inference.json', {'phase': 'started', 'pid': os.getpgrp()})
            raise OSError('lost worker')
        with self.assertRaises(OSError): process_job(self.mentor, job['id'], journal, active)
        self.fault('job_uncertain', lambda: recover_job(self.mentor, job['id'], journal, 'Stopped', retry_inference=True))

    def test_interrupted_verification_is_collected_without_rerun(self):
        job = self.developer_job(); journal = self.root / 'partial'
        recipe = {'argv': [sys.executable, '-c', 'pass'], 'timeout_seconds': 10}
        self.permit_verification(recipe)
        with patch.object(mentor_daemon.subprocess, 'Popen', side_effect=OSError('host stopped')):
            with self.assertRaises(OSError): process_job(self.client, job['id'], journal, self.inference, verification=recipe)
        self.fault('outcome_unknown', lambda: recover_job(self.client, job['id'], journal, 'Stopped'))
        recover_job(self.client, job['id'], journal, 'Process confirmed stopped', collect_interrupted_verification=True)
        with patch.object(mentor_daemon.subprocess, 'Popen', side_effect=AssertionError('Must not rerun verifier')):
            result = process_job(self.client, job['id'], journal, self.inference, verification=recipe)
        state = self.call('get_development_state', {'state_id': result['result']['candidate']})
        self.assertEqual(state['status']['verification'], 'unverified')
        saved = json.loads((journal / digest(job['id']) / 'job.json').read_text())
        self.assertEqual(saved['receipt']['provider']['verification']['exit_code'], -1)
        self.assertIn('Verification interrupted', ' '.join(saved['output']['unverified']))

    def test_failed_coordinator_reuses_completed_specialist_reports(self):
        self.setup_jobs(); self.run_job('specialist'); job = self.job('coordinator'); journal = self.root / 'coordinator'
        def preflight(*args): raise Fault('context_limit', 'Before provider invocation')
        self.fault('context_limit', lambda: process_job(self.mentor, job['id'], journal, preflight))
        j = json.loads((journal / digest(job['id']) / 'job.json').read_text())
        self.mentor.call('fail_mentor_job', {'job_id': job['id'], 'fence': j['job']['fence'], 'reason': 'context_limit'})
        recover_job(self.mentor, job['id'], journal, 'No provider invocation took place')
        self.assertEqual(process_job(self.mentor, job['id'], journal, self.inference)['status'], 'completed')
        self.assertEqual(len([x for x in self.jobs() if x['kind'] == 'specialist']), 1)

    def test_http_recovery_survives_service_restart(self):
        import threading
        from gantry.server import Server
        from gantry.client import Client
        from gantry.service import Service
        job, recipe, journal = self.pause_verified()
        now = self.service.clock()
        restarted = Service(self.root / 'ledger', clock=lambda: now + 901000)
        server = Server(('127.0.0.1', 0), restarted)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        client = Client('http://127.0.0.1:' + str(server.server_port), self.token)
        try:
            recover_job(client, job['id'], journal, 'Previous service and worker stopped')
            result = process_job(client, job['id'], journal, self.inference, verification=recipe)
            self.assertEqual(result['status'], 'completed')
            self.assertTrue(client.call('replay')['matched'])
        finally:
            server.shutdown(); server.server_close(); thread.join()
