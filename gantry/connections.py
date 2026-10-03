"""One owner decision, existing approval events, one atomic activation transaction.

Capability principals can call only the connection facade. They cannot use a
legacy command to bypass project/session/path restrictions or expand authority.
"""
import copy
import re

from .model import require, digest, uid
from .connection_policy import (validate_plan, decode_files, covered, OPERATIONS, clean_bytes,
                                effective_delegation, REVIEW_COUNT_POLICY, CONNECTION_LIMIT_POLICY, connection_expiry)


class ConnectionMixin:
    def _connection_owner(self, actor):
        require(actor['kind'] == 'human' and 'admin' in actor['permissions'],
                'human_approval_required', 'Human owner credential required')

    def _connection_step(self, s, actor, command, args, con, request_id):
        fx, notices = [], []
        result = getattr(self, 'cmd_' + command)(s, actor, args, fx, notices, con)
        return self.store.append(con, s, actor, command, fx, result, {'connection_request': request_id},
            {'type': 'declared', 'text': 'Owner-approved connection setup'}, notices)

    def _connection_approve_changes(self, s, actor, changes, con, cid):
        step = lambda command, args: self._connection_step(s, actor, command, args, con, cid)
        proposal = step('propose', {'title': 'Connection permission: ' + cid, 'changes': changes,
                                  'rationale': 'One explicit owner approval of the fixed connection plan'})
        ref = {'proposal_id': proposal['id'], 'version': proposal['version']}
        step('submit', ref)
        step('endorse', {**ref, 'reason': 'Owner confirmed the fixed permission plan'})
        step('review_adoption', {**ref, 'verdict': 'approve',
                                'reason': 'Permission delegation only; no design adoption'})
        return step('commit', ref)

    def cmd_request_connection(self, s, actor, a, fx, n, con):
        self._connection_owner(actor)
        plan = a['plan']; validate_plan(plan)
        require(plan['expires_at'] is None or self.clock() < plan['expires_at'],
                'invalid_input', 'Explicit connection expiry must be in the future')
        require(all(re.fullmatch('[a-f0-9]{64}', a[k]) for k in ('token_hash', 'mentor_token_hash')), 'invalid_input', 'Token hashes required')
        obj = {'id': uid('connection'), 'status': 'pending', 'owner': actor['id'],
               'plan': plan, 'plan_hash': digest(plan), 'token_hash': a['token_hash'], 'mentor_token_hash': a['mentor_token_hash'],
               'created_at': self.clock()}
        self._put(s, fx, 'agent_connections', obj['id'], obj)
        return {'id': obj['id'], 'status': 'pending', 'plan_hash': obj['plan_hash'], 'active': False}

    def cmd_approve_connection(self, s, actor, a, fx, n, con):
        self._connection_owner(actor)
        obj = copy.deepcopy(s.get('agent_connections', {}).get(a['connection_id']))
        require(obj and obj['owner'] == actor['id'], 'unauthorized', 'Connection owner required')
        require(obj['status'] == 'pending' and obj['plan_hash'] == a['plan_hash'], 'stale_basis', 'Review the pending plan')
        plan = obj['plan']; validate_plan(plan)
        require(plan['expires_at'] is None or self.clock() < plan['expires_at'], 'unauthorized', 'Connection request expired')
        require(decode_files(a['files'], plan['paths']) == plan['files'], 'stale_basis', 'Workspace changed after preview')
        cid = obj['id']; zone = 'project-' + cid.removeprefix('connection_')
        principal = 'agent-' + cid.removeprefix('connection_')
        mentor = 'mentor-' + cid.removeprefix('connection_')
        self._connection_approve_changes(s, actor, [{'id': zone, 'type': 'zone', 'zone': 'root',
            'data': {'owner': actor['id'], 'participation': 'participating'}}], con, cid)
        self._connection_approve_changes(s, actor, [{'id': principal, 'type': 'principal', 'zone': zone,
            'data': {'kind': 'agent', 'permissions': ['read', 'record'] + (['work'] if plan['mode'] == 'work-capable' else []),
                     'zones': [zone], 'token_hash': obj['token_hash'],
                     **({'expires_at': plan['expires_at']} if plan['expires_at'] is not None else {}),
                     'allowed_commands': OPERATIONS, 'connection_id': cid, 'enabled': True}},
            {'id': mentor, 'type': 'principal', 'zone': zone, 'data': {
                'kind': 'agent', 'permissions': ['read', 'propose'], 'zones': [zone],
                'token_hash': obj['mentor_token_hash'],
                **({'expires_at': plan['expires_at']} if plan['expires_at'] is not None else {}),
                'allowed_commands': ['identity', 'get_change_review', 'claim_change_review', 'complete_change_review',
                    'related_review_context', 'read_artifact_chunk', 'list_artifact_files'], 'enabled': True}}], con, cid)
        step = lambda command, args: self._connection_step(s, actor, command, args, con, cid)
        artifact = step('capture_artifact', {'zone': zone, 'files': a['files'],
            'capture_scope': 'approved saved files', 'missing_dependencies': plan['missing']})
        d = step('connect_development', {'title': plan['project'], 'zone': zone, 'snapshot': artifact['revision_id'],
            'capture': {'scope': 'approved saved files', 'missing': plan['missing']},
            'unverified': ['Physical behavior and test outcomes are not verified by connecting'],
            'mode': 'execute' if plan['mode'] == 'work-capable' else 'record', 'actors': [actor['id'], principal, mentor],
            'write_scope': plan['write_paths'], 'recipes': {k: digest(v) for k, v in plan['commands'].items()},
            'max_executions': None, 'timeout_seconds': 300, 'max_parallel': 1})
        state = step('initialize_continuity', {'session_id': d['id'], 'version': d['version'],
            'hierarchy': [{'id': zone, 'title': plan['project'], 'kind': 'project', 'paths': plan['paths'],
                           'editable': plan['mode'] == 'work-capable'}],
            'context': {'requirements': [plan['delegation']['goal'], *plan['delegation']['done']],
                'constraints': ['No network, deletion, hardware or formal adoption', *plan['delegation']['constraints']],
                'decisions': ['Owner approved connection ' + cid], 'open_questions': ['Define engineering acceptance criteria'],
                'environment': {'detected': plan['detected'], 'commands': plan['commands'], 'delegation': plan['delegation']}},
            'summary': 'Connected existing project; earlier development history not inferred'})
        obj.update(status='active', principal=principal, mentor=mentor, zone=zone, session_id=d['id'],
            state_id=state['id'], baseline=state['id'], activated_at=self.clock(), branches={}, tests_used=0, reviews_used=0)
        if plan['mode'] == 'work-capable':
            change = step('begin_change', {'state_id': state['id'], 'title': 'Connected development',
                'purpose': 'Continue within owner-approved scope', 'write_scope': plan['write_paths'],
                'dependencies': [], 'assignee': principal})
            obj['change_id'] = change['id']
            step('configure_review_team', {'session_id': d['id'], 'version': 0, 'coordinator': 'mentor',
                'required_roles': [], 'members': [{'principal_id': principal, 'role': 'developer', 'side': 'user'},
                                                 {'principal_id': mentor, 'role': 'mentor', 'side': 'gantry'}]})
        self._put(s, fx, 'agent_connections', cid, obj)
        return self._connection_public(obj)

    @staticmethod
    def _connection_public(obj):
        result = {k: copy.deepcopy(v) for k, v in obj.items() if k not in {'token_hash', 'mentor_token_hash'}}
        result['effective_delegation'] = effective_delegation(result['plan']['delegation'])
        result['review_count_policy'] = REVIEW_COUNT_POLICY
        result['connection_limit_policy'] = CONNECTION_LIMIT_POLICY
        result['effective_expires_at'] = connection_expiry(obj)
        return result

    @staticmethod
    def _connection_branch(obj, name='main'):
        if name == 'main': return obj
        require(name in obj['branches'], 'not_found', 'Unknown candidate branch')
        return obj['branches'][name]

    def _capability(self, s, actor):
        obj = s.get('agent_connections', {}).get(actor.get('connection_id'))
        require(obj and obj['status'] == 'active' and obj['principal'] == actor['id'], 'unauthorized', 'Active connection required')
        expiry = connection_expiry(obj)
        require(expiry is None or self.clock() < expiry, 'unauthorized', 'Connection expired')
        self._dev_session(s, actor, obj['session_id'])
        return copy.deepcopy(obj)

    def cmd_connection_context(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor)
        from .project_guidance import GUIDANCE
        return {'connection': self._connection_public(obj), 'agent_instructions': GUIDANCE,
                'next': 'Follow saved delegation; checkpoint without asking the owner. Submit a meaningful milestone for Mentor review.',
                'development': self.cmd_get_development_state(s, actor, {'state_id': obj['state_id']}, fx, n, con)}

    def _connection_review_records(self, s, r):
        state = s['dev_states'][r['state_id']]
        expected = digest({p: v['hash'] for p, v in self._manifest(s, state['snapshot']).items()})
        tests = [copy.deepcopy(v) for v in s.get('connection_operations', {}).values()
                 if v['session_id'] == r['session_id'] and v['operation'] == 'test' and
                 v['status'] in {'completed', 'failed'} and v['input_hash'] == expected]
        zone = s['dev_sessions'][r['session_id']]['zone']
        assumptions = [copy.deepcopy(v) for v in s['entries'].values() if v['type'] == 'open_question'
                       and v['zone'] == zone and v['data'].get('kind') == 'provisional_assumption']
        return {'test_observations': sorted(tests, key=lambda x: x['id']),
                'assumptions': sorted(assumptions, key=lambda x: x['id'])}

    def _review_fingerprint(self, s, r):
        original = super()._review_fingerprint(s, r)
        records = self._connection_review_records(s, r)
        return digest([original, records]) if any(records.values()) else original

    def _review_evidence(self, s, r, refs, actor=None, con=None):
        records = self._connection_review_records(s, r)
        extra = {v['id'] for v in records['test_observations']} | {v['revision_id'] for v in records['assumptions']}
        require(refs, 'invalid_input', 'Review evidence required')
        remaining = [ref for ref in refs if ref not in extra]
        if remaining: super()._review_evidence(s, r, remaining, actor, con)

    def cmd_get_change_review(self, s, actor, a, fx, n, con):
        result = super().cmd_get_change_review(s, actor, a, fx, n, con)
        records = self._connection_review_records(s, result)
        if any(records.values()): result['connection_evidence'] = records
        return result

    def cmd_inspect_connection(self, s, actor, a, fx, n, con):
        self._connection_owner(actor)
        obj = s.get('agent_connections', {}).get(a['connection_id'])
        require(obj and obj['owner'] == actor['id'], 'unauthorized', 'Connection owner required')
        return {'connection': self._connection_public(obj), 'operations': [copy.deepcopy(v)
            for v in s.get('connection_operations', {}).values() if v['connection_id'] == obj['id']]}

    def cmd_disconnect_connection(self, s, actor, a, fx, n, con):
        self._connection_owner(actor)
        obj = copy.deepcopy(s.get('agent_connections', {}).get(a['connection_id']))
        require(obj and obj['owner'] == actor['id'], 'unauthorized', 'Connection owner required')
        if obj['status'] == 'revoked': return self._connection_public(obj)
        if obj['status'] == 'active':
            changes = []
            for pid in (obj['principal'], obj['mentor']):
                old = s['entries'][pid]
                changes.append({'id': old['id'], 'type': 'principal', 'zone': old['zone'],
                    'expected_revision': old['revision_id'], 'data': {**old['data'], 'enabled': False}})
            self._connection_approve_changes(s, actor, changes, con, obj['id'])
        obj.update(status='revoked', revoked_at=self.clock())
        self._put(s, fx, 'agent_connections', obj['id'], obj)
        return self._connection_public(obj)

    def cmd_remove_connection_limits(self, s, actor, a, fx, n, con):
        """Explicit owner renewal keeps the existing session/Bot identities and history."""
        self._connection_owner(actor)
        obj = copy.deepcopy(s.get('agent_connections', {}).get(a['connection_id']))
        require(obj and obj['owner'] == actor['id'] and obj['status'] == 'active',
                'unauthorized', 'Active connection owner required; revoked connections cannot be renewed')
        changes = []
        for pid in (obj['principal'], obj['mentor']):
            old = s['entries'][pid]
            require(old['data'].get('enabled', True) and not old.get('retracted'),
                    'unauthorized', 'Disabled credentials cannot be renewed')
            if 'expires_at' in old['data']:
                data = copy.deepcopy(old['data']); data.pop('expires_at')
                changes.append({'id': pid, 'type': 'principal', 'zone': old['zone'],
                    'expected_revision': old['revision_id'], 'data': data})
        if changes: self._connection_approve_changes(s, actor, changes, con, obj['id'])
        d = self._dev_session(s, actor, obj['session_id'])
        if d['max_executions'] is not None:
            from .development import POLICY_FIELDS
            self.cmd_configure_development(s, actor, {'session_id': d['id'], 'version': d['version'],
                **{key: d[key] for key in POLICY_FIELDS}, 'max_executions': None,
                'reason': 'Owner removed local connection execution-count limit'}, fx, n, con)
        obj.update(effective_expires_at=None, limits_removed_by=actor['id'], limits_removed_at=self.clock())
        self._put(s, fx, 'agent_connections', obj['id'], obj)
        return self._connection_public(obj)

    def cmd_authorize_connection_operation(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor); plan = obj['plan']; operation = a['operation']
        require(operation in {'read', 'edit', 'test'}, 'reauthorization_required', 'Operation requires new owner approval')
        require(operation == 'read' or plan['mode'] == 'work-capable', 'unauthorized', 'Record-only cannot edit or execute')
        if operation in {'read', 'edit'}:
            require(covered(a.get('path', ''), plan['write_paths'] if operation == 'edit' else plan['paths']),
                    'reauthorization_required', 'Path not approved')
        if operation == 'test':
            require(a.get('command') in plan['commands'] and a.get('command_hash') == digest(plan['commands'][a['command']]),
                    'reauthorization_required', 'Command not approved')
            obj['tests_used'] += 1; self._put(s, fx, 'agent_connections', obj['id'], obj)
        branch = self._connection_branch(obj, a.get('branch', 'main'))
        if a.get('from_review'):
            review, team = self._review_access(s, actor, a['from_review'])
            require(review['change_id'] == branch.get('change_id') and review['status'] == 'completed'
                    and review['state_id'] == branch['state_id'], 'stale_basis', 'Review is not the current candidate')
            self._review_current(s, review, team)
            if operation == 'edit':
                finding_paths = [p for f in review['output']['findings'] for p in f['paths']]
                require(covered(a['path'], finding_paths), 'scope_denied', 'Edit is not a proposed finding path')
        row = {'id': uid('connectionop'), 'connection_id': obj['id'], 'session_id': obj['session_id'],
               'state_id': branch['state_id'], 'branch': a.get('branch', 'main'), 'operation': operation, 'path': a.get('path'),
               'command': a.get('command'), 'input_hash': a['input_hash'], 'status': 'authorized',
               'created_at': self.clock(), 'review_submission': a.get('from_review')}
        self._put(s, fx, 'connection_operations', row['id'], row)
        return row

    def cmd_complete_connection_operation(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor)
        row = copy.deepcopy(s.get('connection_operations', {}).get(a['operation_id']))
        require(row and row['connection_id'] == obj['id'] and row['status'] == 'authorized', 'invalid_state', 'Operation not pending')
        clean_bytes(a['summary'].encode())
        clean_bytes(str(a['details']).encode())
        row.update(status=a['status'], summary=a['summary'], output_hash=a['output_hash'],
                   details=a['details'], evidence_kind='local_adapter_report', finished_at=self.clock())
        self._put(s, fx, 'connection_operations', row['id'], row)
        return row

    def cmd_connection_checkpoint(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor)
        branch = self._connection_branch(obj, a.get('branch', 'main'))
        require(branch['state_id'] == a['expected_state'], 'stale_basis', 'Connection state changed')
        hashes = decode_files(a['files'], obj['plan']['paths'])
        previous = self._continuity_state(s, actor, branch['state_id'])
        require(set(self._manifest(s, previous['snapshot'])) <= set(hashes), 'reauthorization_required', 'Deletion is not delegated')
        clean_bytes(a['summary'].encode()); clean_bytes(a['rationale'].encode())
        clean_bytes(str(a['unfinished']).encode())
        artifact = self.cmd_capture_artifact(s, actor, {'zone': obj['zone'], 'files': a['files'],
            'capture_scope': 'approved saved files', 'missing_dependencies': obj['plan']['missing']}, fx, n, con)
        capture = {'scope': 'approved saved files', 'missing': obj['plan']['missing']}
        if 'change_id' in branch:
            change = s['dev_changes'][branch['change_id']]
            result = self.cmd_checkpoint_change(s, actor, {'change_id': change['id'], 'version': change['version'],
                'snapshot': artifact['revision_id'], 'summary': a['summary'], 'rationale': a['rationale'],
                'unfinished': a['unfinished'], 'work_status': 'working', 'capture': capture}, fx, n, con)
            state = result['state']
        else:
            d = self._dev_session(s, actor, obj['session_id'])
            state = self._save_state(s, fx, n, d, artifact['revision_id'], [previous['id']], previous['hierarchy'],
                previous['context'], a['summary'], capture, a['unfinished'])
        branch['state_id'] = state['id']; self._put(s, fx, 'agent_connections', obj['id'], obj)
        return {'state': state, 'formal_adoption': False, 'verification': 'unverified'}

    def cmd_connection_submit(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor); branch = self._connection_branch(obj, a.get('branch', 'main'))
        require(obj['plan']['mode'] == 'work-capable', 'mode_disabled', 'Record-only does not request review')
        change = s['dev_changes'][branch['change_id']]
        require(change['checkpoints'], 'invalid_state', 'Checkpoint the milestone before submitting')
        self.cmd_share_change(s, actor, {'change_id': change['id'], 'version': change['version']}, fx, n, con)
        change = s['dev_changes'][branch['change_id']]
        result = self.cmd_submit_change_review(s, actor, {'change_id': change['id'], 'version': change['version'],
            'question': a['question'], 'stage': 'preliminary', 'acceptance': obj['plan']['delegation']['done'], 'required_roles': []}, fx, n, con)
        obj['reviews_used'] += 1; branch['submission_id'] = result['id']
        self._put(s, fx, 'agent_connections', obj['id'], obj)
        return {**result, 'mentor_connection': obj['plan']['delegation']['mentor'], 'formal_adoption': False}

    def cmd_connection_review(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor)
        r = s.get('change_reviews', {}).get(a['submission_id'])
        require(r and r['session_id'] == obj['session_id'], 'unauthorized', 'Review outside connection')
        return self.cmd_get_change_review(s, actor, a, fx, n, con)

    def cmd_connection_respond(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor); branch = self._connection_branch(obj, a.get('branch', 'main'))
        r = s.get('change_reviews', {}).get(a['submission_id'])
        require(r and r['change_id'] == branch.get('change_id'), 'unauthorized', 'Review outside candidate')
        return self.cmd_respond_to_change_review(s, actor, {'submission_id': r['id'], 'candidate_state': branch['state_id'],
            'responses': a['responses']}, fx, n, con)

    def cmd_connection_assumption(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor); branch = self._connection_branch(obj, a.get('branch', 'main'))
        require(all(covered(p, obj['plan']['paths']) for p in a['scope']), 'scope_denied', 'Assumption scope outside project')
        clean_bytes(str(a).encode())
        return self.cmd_record(s, actor, {'type': 'open_question', 'zone': obj['zone'], 'data': {
            'status': 'open', 'kind': 'provisional_assumption', 'development_state': branch['state_id'],
            'blocking': ['continuity:' + obj['session_id']],
            **{k: a[k] for k in ('statement', 'scope', 'evidence', 'dependencies', 'adoption_blocker', 'decision_owner')},
            'accepted_requirement': False, 'physical_safety_guarantee': False}}, fx, n, con)

    def cmd_connection_branch(self, s, actor, a, fx, n, con):
        obj = self._capability(s, actor)
        require(obj['plan']['mode'] == 'work-capable', 'mode_disabled', 'Record-only cannot branch development')
        require(re.fullmatch('[a-zA-Z0-9_-]{1,50}', a['name']) and a['name'] != 'main', 'invalid_input', 'Invalid branch name')
        require(a['name'] not in obj['branches'] and len(obj['branches']) < obj['plan']['delegation']['max_branches'],
                'execution_blocked', 'Branch exists or delegated branch limit reached')
        allowed = {obj['baseline'], obj['state_id']} | {v['state_id'] for v in obj['branches'].values()}
        require(a['base_state'] in allowed, 'scope_denied', 'Choose a state from this connection')
        change = self.cmd_begin_change(s, actor, {'state_id': a['base_state'], 'title': a['name'], 'purpose': a['purpose'],
            'write_scope': obj['plan']['write_paths'], 'dependencies': [], 'assignee': actor['id']}, fx, n, con)
        obj['branches'][a['name']] = {'state_id': a['base_state'], 'base_state': a['base_state'], 'change_id': change['id']}
        self._put(s, fx, 'agent_connections', obj['id'], obj)
        state = s['dev_states'][a['base_state']]
        artifact = self.cmd_restore_artifact(s, actor, {'revision_id': state['snapshot']}, fx, n, con)
        return {'branch': obj['branches'][a['name']], 'artifact': artifact}
