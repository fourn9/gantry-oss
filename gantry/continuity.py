"""Immutable continuation checkpoints over existing artifact and execution records.

All methods use Service's authenticated, idempotent SQLite transaction. A state
contains a complete saved-file composition, not a mutable workspace pointer.
"""
import copy
import difflib
from .development import in_scope
from .model import require, uid, digest, identifier, Fault


class ContinuityMixin:
    def _continuity_state(self, s, actor, sid):
        state = self._dev_get(s, 'dev_states', sid)
        delegated_baseline = any(p.get('baseline_state') == sid and
            s.get('automation_policies', {}).get(p['id'], {}).get('enabled') and
            actor['id'] in s['automation_policies'][p['id']]['analysts'] and
            ('zones' not in actor or p['zone'] in actor['zones']) for p in s.get('product_projects', {}).values())
        if not delegated_baseline: self._dev_session(s, actor, state['session_id'])
        self._dev_artifact(s, state['snapshot'])
        return state

    def _manifest(self, s, snapshot):
        return self._dev_artifact(s, snapshot)['data']['files']

    def _changed(self, s, before, after):
        left, right = self._manifest(s, before), self._manifest(s, after)
        return sorted(p for p in set(left) | set(right)
                      if left.get(p, {}).get('hash') != right.get(p, {}).get('hash'))

    def _save_state(self, s, effects, notices, d, snapshot, parents, hierarchy, context,
                    summary, capture, unfinished, work_status='working', **extra):
        manifest = self._manifest(s, snapshot)
        from .engineering_context import assess
        assess(context, manifest)  # Validate declarations; permit saving failed/unverified work.
        state = dict(id=uid('devstate'), session_id=d['id'], snapshot=snapshot,
            parents=parents, hierarchy=copy.deepcopy(hierarchy), context=copy.deepcopy(context),
            summary=summary, capture=copy.deepcopy(capture), unfinished=unfinished,
            work_status=work_status, created_at=self.clock(), **extra)
        # Component versions are immutable content combinations, including deletions.
        state['components'] = {node['id']: {'version': digest({p: info['hash'] for p, info in manifest.items()
            if in_scope(p, node['paths'])}), 'files': [p for p in sorted(manifest) if in_scope(p, node['paths'])],
            'storage': ('bytes_saved' if any(in_scope(p, node['paths']) for p in manifest) else
                        'external_reference_only' if node.get('external_uri') else
                        'structure_only' if not node['paths'] else 'not_acquired'),
            'editable': node['editable']} for node in hierarchy}
        self._dev_save(s, effects, 'dev_states', state)
        self._milestone(s, effects, notices, d, 'checkpoint', summary, [state['id'], snapshot])
        return state

    def cmd_initialize_continuity(self, s, actor, a, fx, n, con):
        d = self._dev_session(s, actor, a['session_id']); self.allowed(actor, 'record')
        require(d['version'] == a['version'], 'stale_basis', 'Development changed')
        require(not d.get('active_state'), 'conflict', 'Already initialized')
        nodes = a['hierarchy']; ids = [identifier(node['id']) for node in nodes]
        require(len(set(ids)) == len(ids), 'invalid_input', 'Duplicate hierarchy ID')
        for node in nodes:
            self._dev_paths(node['paths'], True)
            seen = {node['id']}; parent = node.get('parent')
            while parent:
                require(parent in ids and parent not in seen, 'invalid_input', 'Invalid hierarchy parent or cycle')
                seen.add(parent); parent = next(x for x in nodes if x['id'] == parent).get('parent')
        state = self._save_state(s, fx, n, d, d['snapshot'], [], nodes, a['context'], a['summary'],
                                d['capture'], d['unverified'])
        d['active_state'] = state['id']; d['version'] += 1
        self._dev_save(s, fx, 'dev_sessions', d)
        return state

    def cmd_get_development_state(self, s, actor, a, fx, n, con):
        state = self._continuity_state(s, actor, a['state_id'])
        manifest = self._manifest(s, state['snapshot'])
        evaluations = []
        for item in s.get('dev_evaluations', {}).values():
            if item['session_id'] != state['session_id']: continue
            e = s.get('dev_executions', {}).get(item['execution_id'], {})
            c = s.get('dev_contracts', {}).get(e.get('contract_id'), {})
            valid = bool(e.get('valid') and c.get('submission', {}).get('valid'))
            try:
                self._dev_artifact(s, e.get('output_snapshot'))
            except Fault:
                valid = False
            evaluations.append({**item, 'applicable': item['state_id'] == state['id'] and valid})
        applicable = [x for x in evaluations if x['applicable']]
        shares = [x for x in s.get('dev_shares', {}).values() if x['state_id'] == state['id']]
        adoptions = [e for e in s['entries'].values() if e['type'] == 'design_document'
                     and not e.get('retracted') and e['data'].get('development_state') == state['id']]
        restores = [r for r in s.get('dev_restores', {}).values() if r['state_id'] == state['id']]
        verification = ('fail' if any(e['verdict'] == 'fail' for e in applicable) else
                        'pass' if applicable and all(e['verdict'] == 'pass' for e in applicable) else
                        'unknown' if applicable else 'unverified')
        diffs = []
        before = self._manifest(s, s['dev_states'][state['parents'][0]]['snapshot']) if state['parents'] else {}
        preview_budget = 262144
        for path in sorted(set(before) | set(manifest)):
            left, right = before.get(path), manifest.get(path)
            if (left or {}).get('hash') == (right or {}).get('hash'): continue
            diff = {'path': path, 'before': (left or {}).get('hash'), 'after': (right or {}).get('hash'),
                    'kind': 'added' if left is None else 'deleted' if right is None else 'modified'}
            size = sum(info['size'] for info in (left, right) if info)
            if size <= min(preview_budget, 65536):
                try:
                    texts = [b''.join(self.store.verified_parts(info)).decode('utf-8') if info else '' for info in (left, right)]
                    if all('\x00' not in t for t in texts):
                        diff['text'] = ''.join(difflib.unified_diff(texts[0].splitlines(True), texts[1].splitlines(True),
                            fromfile='before/'+path, tofile='after/'+path))
                        preview_budget -= size
                except UnicodeDecodeError: pass
            if 'text' not in diff: diff['preview'] = 'binary_or_size_limit; restore saved files for inspection'
            diffs.append(diff)
        return {'state': state, 'manifest': manifest, 'evaluations': evaluations, 'shares': shares,
            'diffs': diffs,
            'restores': restores, 'adoptions': adoptions,
            'status': {'work': state['work_status'],
                'sharing': 'integrated' if state.get('integrated_changes') else 'shared' if shares else 'local',
                'verification': verification, 'verification_scope': [e['scope'] for e in applicable],
                'adoption': 'human_adopted' if adoptions else 'unadopted'},
            'storage': 'restore_verified' if restores else 'bytes_saved',
            'restore': {'command': 'restore-development-state', 'state_id': state['id'],
                        'snapshot': state['snapshot'], 'destination_must_be_new': True}, 'seq': s['seq']}

    def cmd_list_development_states(self, s, actor, a, fx, n, con):
        d = self._dev_session(s, actor, a['session_id'])
        states = [v for v in s.get('dev_states', {}).values() if v['session_id'] == d['id']]
        states.sort(key=lambda v: (v['created_at'], v['id']), reverse=True)
        offset, limit = a.get('offset', 0), a.get('limit', 50)
        return {'active_state': d.get('active_state'), 'total': len(states),
            'states': states[offset:offset+limit], 'changes': [v for v in s.get('dev_changes', {}).values()
            if v['session_id'] == d['id']], 'next_offset': offset+limit if offset+limit < len(states) else None}

    def cmd_begin_change(self, s, actor, a, fx, n, con):
        state = self._continuity_state(s, actor, a['state_id']); self.allowed(actor, 'work')
        d = self._dev_session(s, actor, state['session_id'])
        require(a['assignee'] in d['actors'] or a['assignee'] == d['owner'], 'unauthorized', 'Assignee is not a participant')
        self._dev_paths(a['write_scope'], True); self._dev_paths(a['dependencies'])
        require(a['write_scope'], 'invalid_input', 'Write scope required')
        manifest = self._manifest(s, state['snapshot'])
        require(set(a['dependencies']) <= set(manifest), 'invalid_input', 'Dependency not in baseline')
        obj = dict(a, id=uid('change'), version=1, session_id=d['id'], base_state=state['id'],
            head=state['id'], author=actor['id'], status='working', sharing='local', checkpoints=[],
            dependency_hashes={p: manifest[p]['hash'] for p in a['dependencies']})
        return self._dev_save(s, fx, 'dev_changes', obj)

    def _change(self, s, actor, a):
        change = self._dev_get(s, 'dev_changes', a['change_id'])
        self._dev_session(s, actor, change['session_id']); self.allowed(actor, 'work')
        require(actor['id'] in {change['assignee'], change['author']} or 'admin' in actor['permissions'],
                'unauthorized', 'Only change author or assignee may update it; start a new change to continue')
        require(change['version'] == a['version'], 'stale_basis', 'Change advanced')
        require(change['sharing'] != 'integrated', 'invalid_state', 'Start a new change after integration')
        return change

    def cmd_checkpoint_change(self, s, actor, a, fx, n, con):
        change = self._change(s, actor, a); self.allowed(actor, 'record')
        base = self._continuity_state(s, actor, change['base_state'])
        previous = self._continuity_state(s, actor, change['head'])
        changed = self._changed(s, base['snapshot'], a['snapshot'])
        require(all(in_scope(p, change['write_scope']) for p in changed), 'scope_denied', 'Changes outside declared scope')
        for wid in a.get('work_ids', []):
            require(wid in s.get('dev_contracts', {}) and s['dev_contracts'][wid]['session_id'] == base['session_id'],
                    'invalid_input', 'Unknown work contract')
        d = self._dev_session(s, actor, base['session_id'])
        context = a.get('context', previous['context'])
        if a.get('engineering_review'):
            review, team = self._review_access(s, actor, a['engineering_review'])
            self._member(team, actor, 'user')
            self._review_current(s, review, team)
            require(review['change_id'] == change['id'] and actor['id'] == change['assignee'],
                    'unauthorized', 'Engineering proposal belongs to another change or assignee')
            require(review['status'] == 'completed', 'review_pending', 'Complete review before applying its proposal')
            require('context' not in a, 'invalid_input', 'Apply inferred declarations without replacing existing context')
            from .engineering_proposals import candidate_context
            context = candidate_context(previous['context'], review.get('engineering_proposal'), self._manifest(s, a['snapshot']))
        state = self._save_state(s, fx, n, d, a['snapshot'], [previous['id']], base['hierarchy'],
            context, a['summary'], a['capture'], a['unfinished'], a['work_status'],
            change_id=change['id'], rationale=a['rationale'], changed_paths=changed, work_ids=a.get('work_ids', []))
        change.update(head=state['id'], version=change['version']+1, sharing='local', status=a['work_status'])
        change['checkpoints'].append(state['id']); self._dev_save(s, fx, 'dev_changes', change)
        return {'state': state, 'change': change}

    def cmd_share_change(self, s, actor, a, fx, n, con):
        change = self._change(s, actor, a); self.allowed(actor, 'record')
        require(change['checkpoints'], 'invalid_state', 'Checkpoint before sharing')
        receipt = dict(id=uid('share'), session_id=change['session_id'], state_id=change['head'],
            change_id=change['id'], change_version=change['version'], actor=actor['id'], at=self.clock())
        self._dev_save(s, fx, 'dev_shares', receipt)
        change.update(sharing='shared', version=change['version']+1)
        self._dev_save(s, fx, 'dev_changes', change)
        return {'share': receipt, 'change': change}

    def cmd_integrate_changes(self, s, actor, a, fx, n, con):
        target = self._continuity_state(s, actor, a['state_id']); self.allowed(actor, 'work'); self.allowed(actor, 'record')
        d = self._dev_session(s, actor, target['session_id'])
        require(len({x['id'] for x in a['changes']}) == len(a['changes']), 'invalid_input', 'Duplicate change')
        original = self._manifest(s, target['snapshot']); merged = copy.deepcopy(original)
        owners = {}; conflicts = []; selected = []; unfinished = list(target['unfinished'])
        context = copy.deepcopy(target['context']); context_owners = {}
        capture_missing = list(target['capture']['missing'])
        for ref in a['changes']:
            change = self._dev_get(s, 'dev_changes', ref['id'])
            require(change['session_id'] == d['id'], 'invalid_input', 'Cross-project integration unsupported')
            require(change['version'] == ref['version'], 'stale_basis', 'Change advanced')
            require(change['sharing'] == 'shared', 'invalid_state', 'Share this checkpoint before integration')
            base = self._continuity_state(s, actor, change['base_state'])
            head = self._continuity_state(s, actor, change['head'])
            base_files, files = self._manifest(s, base['snapshot']), self._manifest(s, head['snapshot'])
            for path in self._changed(s, base['snapshot'], head['snapshot']):
                if path in owners or original.get(path, {}).get('hash') != base_files.get(path, {}).get('hash'):
                    conflicts.append({'path': path, 'reason': 'concurrent_change', 'change': change['id']})
                owners[path] = change['id']
                if path in files: merged[path] = copy.deepcopy(files[path])
                else: merged.pop(path, None)
            for key, value in head['context'].items():
                if value == base['context'][key]: continue
                if key in context_owners or target['context'][key] != base['context'][key]:
                    conflicts.append({'path': 'context.'+key, 'reason': 'concurrent_context', 'change': change['id']})
                context_owners[key] = change['id']; context[key] = copy.deepcopy(value)
            selected.append((change, head)); unfinished.extend(head['unfinished'])
            capture_missing.extend(head['capture']['missing'])
        for change, head in selected:
            head_files = self._manifest(s, head['snapshot'])
            for path, h in change['dependency_hashes'].items():
                # A change may read and intentionally replace the same input.
                # Its baseline was checked above; its own saved output is the
                # expected final value. Other read dependencies stay pinned.
                expected = (head_files.get(path, {}).get('hash')
                            if owners.get(path) == change['id'] else h)
                if merged.get(path, {}).get('hash') != expected:
                    conflicts.append({'path': path, 'reason': 'dependency_changed', 'change': change['id']})
        if conflicts:
            return {'integrated': False, 'conflicts': conflicts, 'basis': target['id'],
                    'changes': a['changes'], 'note': 'No candidate or change head was modified'}
        artifact = self._entry(uid('artifact'), 'artifact_snapshot', d['zone'],
            {'files': merged, 'capture_scope': 'integrated_saved_manifests',
             'missing_dependencies': sorted(set(capture_missing)), 'restorable': True,
             'source': {'states': [target['id']] + [h['id'] for _, h in selected]}}, None)
        self._save_entry(s, fx, artifact)
        unfinished.append('Physical compatibility of combined changes has not been established')
        state = self._save_state(s, fx, n, d, artifact['revision_id'],
            [target['id']] + [h['id'] for _, h in selected], target['hierarchy'], context, a['summary'],
            {'scope': 'integrated saved files', 'missing': sorted(set(capture_missing))}, sorted(set(unfinished)),
            integrated_changes=[{'id': c['id'], 'version': c['version'], 'state_id': h['id']} for c, h in selected],
            compatibility='unknown', changed_paths=self._changed(s, target['snapshot'], artifact['revision_id']))
        for change, _ in selected:
            change.update(sharing='integrated', integrated_into=state['id'], version=change['version']+1)
            self._dev_save(s, fx, 'dev_changes', change)
        return {'integrated': True, 'state': state, 'conflicts': [], 'compatibility': 'unknown'}

    def cmd_select_development_state(self, s, actor, a, fx, n, con):
        state = self._continuity_state(s, actor, a['state_id'])
        d = self._dev_session(s, actor, state['session_id'])
        # Reuse v0.11 generation invalidation and execution policy version checks.
        result = self.cmd_advance_development(s, actor, {'session_id': d['id'], 'version': a['version'],
            'snapshot': state['snapshot'], 'reason': a['reason'], 'capture': state['capture'],
            'unverified': state['unfinished']}, fx, n, con)
        result['active_state'] = state['id']; self._dev_save(s, fx, 'dev_sessions', result)
        return result

    def cmd_propose_state_adoption(self, s, actor, a, fx, n, con):
        state = self._continuity_state(s, actor, a['state_id'])
        d = self._dev_session(s, actor, state['session_id'])
        eid = 'continuity:' + d['id']; prior = s['entries'].get(eid)
        return self.cmd_propose(s, actor, {'title': 'Adopt development state: ' + state['summary'],
            'rationale': a['reason'], 'changes': [{'id': eid, 'type': 'design_document', 'zone': d['zone'],
            'expected_revision': prior['revision_id'] if prior else None,
            'data': {'title': state['summary'], 'development_state': state['id'], 'snapshot': state['snapshot'],
                     'unresolved_at_proposal': state['unfinished']}}]}, fx, n, con)

    def cmd_record_state_evaluation(self, s, actor, a, fx, n, con):
        state = self._continuity_state(s, actor, a['state_id']); self.allowed(actor, 'record')
        e = self._dev_get(s, 'dev_executions', a['execution_id'])
        require(e['session_id'] == state['session_id'] and e.get('input_state') == state['id']
                and e['input_snapshot'] == state['snapshot'] and e['status'] in {'completed', 'failed'},
                'invalid_input', 'Evaluation must be a terminal execution of this exact state')
        c = s.get('dev_contracts', {}).get(e.get('contract_id'), {})
        require(c.get('completion', {}).get('verdict_file'), 'invalid_input', 'A declared verdict evaluator is required')
        # An evaluator must not silently edit its own inputs and claim it tested the original.
        inputs = self._manifest(s, state['snapshot'])
        require(not set(e['changed_paths']) & set(inputs), 'evidence_invalid', 'Execution changed evaluated inputs')
        evaluation = {**a, 'id': uid('evaluation'), 'session_id': state['session_id'],
            'input_snapshot': state['snapshot'], 'result_snapshot': e['output_snapshot'],
            'verdict': e['engineering_verdict'], 'at': self.clock(), 'actor': actor['id']}
        return self._dev_save(s, fx, 'dev_evaluations', evaluation)

    def cmd_record_state_restore(self, s, actor, a, fx, n, con):
        state = self._continuity_state(s, actor, a['state_id']); self.allowed(actor, 'record')
        expected = {p: v['hash'] for p, v in self._manifest(s, state['snapshot']).items()}
        require(a['hashes'] == expected, 'integrity_error', 'Restored file inventory/hash mismatch')
        receipt = {**a, 'id': uid('restore'), 'session_id': state['session_id'], 'actor': actor['id'],
            'at': self.clock(), 'verification': 'adapter_reported_file_hashes',
            'environment_verified': False}
        return self._dev_save(s, fx, 'dev_restores', receipt)

    def cmd_mentor_reflect(self, s, actor, a, fx, n, con):
        self._dev_session(s, actor, a['session_id']); self.allowed(actor, 'propose')
        c = self._dev_get(s, 'dev_contracts', a['contract_id'])
        require(c['session_id'] == a['session_id'] and c.get('submission'), 'invalid_input', 'Submitted work required')
        return self._dev_save(s, fx, 'dev_reflections', {**a, 'id': uid('reflection'),
            'evidence': copy.deepcopy(c['submission']), 'input_state': c.get('input_state'),
            'actor': actor['id'], 'at': self.clock(), 'explanation_type': 'submitted'})
