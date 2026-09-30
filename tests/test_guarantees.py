import copy
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import test_service as fixtures
from gantry.backup import restore_backup
from gantry.model import Fault, canonical
from gantry.service import Service, token_hash


class GuaranteeTests(unittest.TestCase):
    setUp = fixtures.LedgerTests.setUp
    tearDown = fixtures.LedgerTests.tearDown
    call = fixtures.LedgerTests.call
    proposal = fixtures.LedgerTests.proposal
    approve = fixtures.LedgerTests.approve
    commit = fixtures.LedgerTests.commit
    submit = fixtures.LedgerTests.submit
    assertFault = fixtures.LedgerTests.assertFault

    def adopt(self, changes):
        p = self.call('propose', {'title': 'setup', 'changes': changes})
        self.submit(p); self.approve(p); self.commit(p)
        return p

    def change(self, eid, data):
        old = self.call('state')['entries'][eid]
        return {'id': eid, 'type': old['type'], 'zone': old['zone'],
                'data': data, 'expected_revision': old['revision_id']}

    def setup_zones(self):
        self.adopt([{'id': 'mechanical', 'type': 'zone', 'data': {'owner': 'admin'}},
                    {'id': 'control', 'type': 'zone', 'data': {'owner': 'admin'}}])

    def test_consent_deadline_and_objection(self):
        self.setup_zones()
        p = self.call('propose', {'title': 'joint', 'changes': [
            {'id': 'hand', 'type': 'subsystem', 'zone': 'mechanical', 'data': {}},
            {'id': 'controller', 'type': 'subsystem', 'zone': 'control', 'data': {}}]})
        self.submit(p)
        args = {'proposal_id': p['id'], 'version': 1, 'reason': 'review'}
        self.call('review_adoption', {**args, 'verdict': 'approve'})
        self.assertFault('review_pending', lambda: self.commit(p))
        self.call('object', args)
        self.now += 3600001
        self.assertFault('review_pending', lambda: self.commit(p))
        self.call('retract_review', args)
        self.commit(p)

    def test_external_silence_never_approves(self):
        self.adopt([{'id': 'supplier', 'type': 'zone', 'data': {'participation': 'external'}}])
        p = self.call('propose', {'title': 'external part', 'changes': [
            {'id': 'part', 'type': 'part_spec', 'zone': 'supplier', 'data': {}}]})
        self.submit(p); self.now += 9000000
        self.assertFault('blocked_external', lambda: self.commit(p))
        self.adopt([self.change('supplier', {'participation': 'external', 'proxy_owner': 'admin',
                                            'proxy_reason': 'Explicit delegated review'})])
        self.assertFault('stale_basis', lambda: self.commit(p))
        p = self.call('rebase', {'proposal_id': p['id'], 'version': 1})
        self.submit(p); self.approve(p); self.commit(p)

    def setup_dependency(self):
        self.adopt([{'id': 'hand', 'type': 'subsystem', 'data': {'mass': 1}},
                    {'id': 'controller', 'type': 'subsystem', 'data': {'gain': 1}},
                    {'id': 'dependency', 'type': 'relation', 'data': {
                        'kind': 'depends_on', 'source': 'controller', 'target': 'hand'}}])

    def test_upstream_commit_invalidates_downstream_without_same_target(self):
        self.setup_dependency()
        downstream = self.call('propose', {'title': 'gain', 'changes': [self.change('controller', {'gain': 2})]})
        self.submit(downstream); self.approve(downstream)
        self.call('record', {'type': 'eval_result', 'data': {'run_id': 'unrelated'}})
        self.assertEqual(self.call('state')['proposals'][downstream['id']]['status'], 'reviewing')
        self.adopt([self.change('hand', {'mass': 2})])
        self.assertFault('stale_basis', lambda: self.commit(downstream))

    def test_relation_removal_keeps_old_impact(self):
        self.setup_zones()
        self.adopt([{'id': 'hand', 'type': 'subsystem', 'zone': 'mechanical', 'data': {}},
                    {'id': 'controller', 'type': 'subsystem', 'zone': 'control', 'data': {}},
                    {'id': 'dependency', 'type': 'relation', 'data': {
                        'kind': 'depends_on', 'source': 'controller', 'target': 'hand'}}])
        change = self.change('dependency', {'kind': 'depends_on', 'source': 'controller', 'target': 'hand'})
        p = self.call('propose', {'title': 'remove relation', 'changes': [{**change, 'retracted': True}]})
        self.assertTrue({'mechanical', 'control'} <= set(self.call('impact', {'proposal_id': p['id']})['zones']))

    def test_reservation_expires_and_does_not_approve(self):
        p = self.proposal('hand'); q = self.proposal('controller')
        self.submit(p); self.submit(q); self.approve(q)
        self.call('reserve', {'proposal_id': p['id'], 'seconds': 1})
        self.assertFault('reserved', lambda: self.commit(q))
        self.assertFault('review_pending', lambda: self.commit(p))
        self.now += 1001
        self.commit(q)

    def test_required_validation_is_bound_to_candidate(self):
        p = self.call('propose', {'title': 'validated', 'changes': [
            {'id': 'testplan', 'type': 'validation_plan', 'data': {'required': True}}]})
        self.submit(p); self.approve(p)
        self.assertFault('validation_required', lambda: self.commit(p))
        rid = p['changes'][0]['revision_id']
        self.call('record', {'type': 'eval_result', 'data': {'run_id': 'test', 'validation_plan': rid,
                   'design_revision': p['candidate_id'], 'verdict': 'pass'}})
        self.commit(p)

    def test_restore_preserves_write_idempotency(self):
        args = {'title': 'one', 'changes': [{'id': 'hand', 'type': 'subsystem', 'data': {}}]}
        original = self.call('propose', args, key='durable-key')
        bundle = self.call('export')
        restored_dir = Path(self.temp.name) / 'restored'
        restore_backup(restored_dir, bundle)
        restored = Service(restored_dir)
        self.assertEqual(restored.call(self.token, 'propose', args, 'durable-key'), original)
        self.assertEqual(restored.call(self.token, 'state')['seq'], bundle['checkpoint']['seq'])
        self.assertFault('idempotency_mismatch', lambda: restored.call(self.token, 'propose', {**args, 'title': 'other'}, 'durable-key'))

    def test_replay_repairs_corrupt_projection_using_log_identity(self):
        p = self.proposal(); self.submit(p); self.approve(p); self.commit(p)
        with self.svc.store.connect() as con:
            state = self.svc.store.state(con)
            state['head'] = 'corrupted'
            state['principals'] = {}
            con.execute('UPDATE projection SET body=?', (canonical(state),))
        result = self.call('replay')
        self.assertTrue(result['repaired'])
        self.assertNotEqual(self.call('state')['head'], 'corrupted')
        self.assertTrue(self.call('verify')['valid'])

    def test_retracted_principal_cannot_authenticate(self):
        token = secrets.token_urlsafe(32)
        self.adopt([{'id': 'reader', 'type': 'principal', 'data': {
            'kind': 'agent', 'permissions': ['read'], 'token_hash': token_hash(token)}}])
        old = self.call('state')['entries']['reader']
        # Credential hash is intentionally not exposed by state.
        change = self.change('reader', {**old['data'], 'token_hash': token_hash(token)})
        self.adopt([{**change, 'retracted': True}])
        self.assertFault('unauthorized', lambda: self.call('state', token=token))

    def test_distinct_concurrent_commits_only_apply_once(self):
        p = self.proposal(); self.submit(p); self.approve(p)
        def commit(_):
            try: return self.commit(p)
            except Fault as exc: return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(commit, range(2)))
        self.assertEqual(sum(isinstance(x, dict) for x in results), 1)
        self.assertIn('invalid_state', results)


if __name__ == '__main__': unittest.main()
