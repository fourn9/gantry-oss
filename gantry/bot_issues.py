"""Bot-authored residual issue lifecycle; no engineering dispatcher or adoption."""
import copy
import json

from .contracts import register, S, I, A, validate
from .development import in_scope
from .engineering_context import assess
from .model import require, digest, uid, Fault
from .requirement_traceability import stale_refs, _subset_refs, REFS

IDS = {**A, 'maxItems': 40}
PAGE = {'after': S, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}
OPEN = {'task_id': S, 'fence': S, 'source_task_id': S, 'source_attempt': I, 'followup_id': S,
    'owner_bot_id': S, 'paths': {**IDS, 'minItems': 1}, 'completion': {**IDS, 'minItems': 1},
    'verification_plan': S, 'check_ids': {**IDS, 'minItems': 1}}
register('open_bot_issue', OPEN, list(OPEN))
register('review_bot_issue', {'task_id': S, 'fence': S, 'issue_id': S, 'version': I,
    'status': {'enum': ['working', 'verifying', 'deferred', 'reopened', 'resolved']},
    'state_id': S, 'reason': S, 'evidence': IDS, 'verification_task_ids': IDS,
    'reassessment': {'type':'object', 'properties':{'verification_plan':S, 'check_ids':{**IDS,'minItems':1}, 'requirement_refs':REFS},
        'required':['verification_plan','check_ids','requirement_refs'], 'additionalProperties':False}},
    ['task_id', 'fence', 'issue_id', 'version', 'status', 'state_id', 'reason', 'evidence'])
register('get_bot_issue', {'task_id': S, 'issue_id': S, 'state_id': S, **PAGE}, ['task_id', 'issue_id'])
register('list_bot_issues', {'task_id': S, 'state_id': S, **PAGE}, ['task_id'])


class BotIssuesMixin:
    def _issue_access(self, s, actor, issue):
        states = [issue['baseline_state']]
        source = s['bot_tasks'][issue['source_task_id']]
        states.extend(r['state_id'] for r in source['reports'] if r['attempt'] == issue['source_attempt'])
        if issue.get('resolution'): states.append(issue['resolution']['state_id'])
        for ident in set(states): self._continuity_state(s, actor, ident)

    def _issue_readable(self, s, actor, issue):
        try: self._issue_access(s, actor, issue); return True
        except Fault as exc:
            if exc.code in {'unauthorized','scope_denied'}: return False
            raise

    def _issue_state(self, s, actor, task, ident):
        state = self._continuity_state(s, actor, ident)
        require(state['session_id'] == task['session_id'], 'scope_denied', 'Issue state belongs to another project')
        return state

    def _issue_authority(self, s, actor, task, owner):
        binding, _, _, _ = self._bd_actor(s, actor, task['session_id'], task['bot_id'])
        require(task.get('studio_mode') != 'ask' and not task.get('reply_request_id'),
                'scope_denied', 'Read-only consultation cannot change an issue')
        require(task['bot_id'] == owner or binding['can_assign'] and self._bd_subordinate(s, task['bot_id'], owner),
                'unauthorized', 'Responsible Bot or its delegated manager required')
        responsible = self._bd_binding(s, task['session_id'], owner)
        if task['bot_id'] == owner:
            require(responsible['enabled'] and s['persistent_bots'][owner]['enabled'], 'mode_disabled', 'Issue owner is disabled')

    def _issue_event(self, s, fx, issue, task, kind, **details):
        return self._dev_save(s, fx, 'bot_issue_events', dict(id=uid('bievent'), subject_id=issue['id'],
            issue_id=issue['id'], session_id=issue['session_id'], task_id=task['id'],
            bot_id=task['bot_id'], principal_id=task['principal_id'], issue_version=issue['version'],
            kind=kind, created_seq=s['seq']+1, at=self.clock(), **details))

    def _issue_assignment(self, s, actor, task, fx):
        ids = task.get('issue_ids', [])
        require(len(ids) <= 40 and len(set(ids)) == len(ids), 'invalid_input', 'Distinct bounded issue links required')
        for ident in ids:
            issue = self._dev_get(s, 'bot_issues', ident)
            require(issue['session_id'] == task['session_id'], 'scope_denied', 'Issue belongs to another project')
            self._issue_access(s, actor, issue)
            require({r['requirement_id'] for r in issue['requirement_refs']} <=
                    {r['requirement_id'] for r in task.get('requirement_refs', [])},
                    'invalid_input', 'Issue requirements must reach the assignment; revised requirements need explicit reassessment')
            self._issue_event(s, fx, issue, task, 'assignment', linked_task_id=task['id'])

    def _issue_plan(self, s, state, plan_path, check_ids, paths, refs):
        manifest = self._manifest(s, state['snapshot'])
        self.store.safe_name(plan_path)
        info = manifest.get(plan_path)
        require(info and info['size'] <= 1024**2, 'invalid_input', 'Saved bounded acceptance plan required')
        try: plan = json.loads(b''.join(self.store.verified_parts(info)))
        except (ValueError, UnicodeError): require(False, 'invalid_input', 'Invalid acceptance plan JSON')
        require(isinstance(plan, dict) and set(plan) == {'version','components','checks'} and plan.get('version') == 1
                and isinstance(plan.get('components'), list) and 1 <= len(plan['components']) <= 100
                and isinstance(plan.get('checks'), list) and 1 <= len(plan['checks']) <= 100,
                'invalid_input', 'Physical evidence plan v1 required')
        components = {}
        for component in plan['components']:
            require(isinstance(component, dict) and isinstance(component.get('id'), str) and component['id']
                    and component['id'] not in components and isinstance(component.get('role'), str)
                    and isinstance(component.get('assembly'), str) and isinstance(component.get('paths'), list)
                    and component['paths'] and all(isinstance(p,str) and p in manifest for p in component['paths']),
                    'invalid_input', 'Complete distinct component declarations required')
            components[component['id']] = component['paths']
        checks = {c['id']: c for c in plan['checks'] if isinstance(c, dict) and isinstance(c.get('id'), str)}
        require(len(checks) == len(plan['checks']) and len(set(check_ids)) == len(check_ids)
                and set(check_ids) <= set(checks), 'invalid_input', 'Distinct existing check IDs required')
        selected = [checks[i] for i in check_ids]
        from .physical_evidence import evaluate
        for check in selected:
            require(isinstance(check.get('scope'), str) and check['scope'] in {'placement','motion','service','connection','structural','electrical','thermal','other'}
                    and type(check.get('required')) is bool and isinstance(check.get('components'), list) and check['components']
                    and all(isinstance(c,str) and c in components for c in check['components'])
                    and isinstance(check.get('report'), str), 'invalid_input', 'Complete physical check declaration required')
            self.store.safe_name(check['report'])
            evaluate(check, None, {p:v['hash'] for p,v in manifest.items()})
            require(all(set(components[c]) <= set(check['inputs']) for c in check['components']),
                    'invalid_input', 'Check must bind its component inputs')
            validate(check.get('requirement_refs', []), REFS)
            _subset_refs(state['context'].get('requirement_refs', []), check.get('requirement_refs', []))
        require(all(isinstance(c.get('inputs'), list) and c['inputs'] and all(p in manifest for p in c['inputs']) for c in selected),
                'invalid_input', 'Checks must name saved inputs')
        require(set(paths) <= {p for c in selected for p in c['inputs']}, 'invalid_input', 'Checks must cover affected files')
        require(all(any(ref in c.get('requirement_refs', []) for c in selected) for ref in refs),
                'invalid_input', 'Checks must cover issue requirements')
        return {'path': plan_path, 'sha256': info['hash']}, copy.deepcopy(selected)

    def cmd_open_bot_issue(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        self._issue_authority(s, actor, task, a['owner_bot_id'])
        source = self._dev_get(s, 'bot_tasks', a['source_task_id'])
        require(source['session_id'] == task['session_id'], 'scope_denied', 'Source belongs to another project')
        self._issue_authority(s, actor, task, source['bot_id'])
        report = next((r for r in source['reports'] if r['attempt'] == a['source_attempt']), None)
        item = next((x for x in ((report or {}).get('report', {}).get('followups') or []) if x['id'] == a['followup_id']), None)
        require(item is not None, 'not_found', 'Saved report follow-up required')
        self._continuity_state(s, actor, report['state_id'])
        key = 'bissue_' + digest([task['session_id'], source['id'], report['seq'], a['followup_id']])
        declaration = {k: copy.deepcopy(a[k]) for k in OPEN if k not in {'task_id', 'fence'}}
        old = s.get('bot_issues', {}).get(key)
        if old:
            self._issue_access(s, actor, old)
            require(old['declaration'] == declaration, 'conflict', 'Issue already promoted with another contract')
            return copy.deepcopy(old)
        state = self._issue_state(s, actor, task, task.get('output_state', task['state_id']))
        manifest = self._manifest(s, state['snapshot'])
        self._dev_paths(a['paths']); self.store.safe_name(a['verification_plan'])
        require(len(set(a['paths'])) == len(a['paths']) and all(p in manifest for p in a['paths']),
                'invalid_input', 'Affected paths must identify distinct saved files')
        owner = self._bd_binding(s, task['session_id'], a['owner_bot_id'])
        require(all(in_scope(p, task['write_scope']) and in_scope(p, owner['write_scope']) for p in a['paths']),
                'scope_denied', 'Issue scope exceeds task or responsible Bot scope')
        _subset_refs(task.get('requirement_refs', []), item['requirement_refs'])
        plan_binding, selected = self._issue_plan(s, state, a['verification_plan'], a['check_ids'], a['paths'], item['requirement_refs'])
        issue = dict(id=key, session_id=task['session_id'], subject_id=a['owner_bot_id'],
            owner_bot_id=a['owner_bot_id'], source_task_id=source['id'], source_attempt=report['attempt'],
            source_seq=report['seq'], followup_id=item['id'], summary=item['summary'], source_reason=item['reason'],
            source_evidence=copy.deepcopy(item['evidence']), requirement_refs=copy.deepcopy(item['requirement_refs']),
            paths=copy.deepcopy(a['paths']), completion=copy.deepcopy(a['completion']), checks=copy.deepcopy(selected),
            verification_plan=plan_binding,
            baseline_state=state['id'], status='open', version=1, created_seq=s['seq']+1,
            cycle_started_seq=s['seq']+1, declaration=declaration)
        self._dev_save(s, fx, 'bot_issues', issue)
        self._issue_event(s, fx, issue, task, 'opened', state_id=state['id'], reason='Bot supplied operational acceptance from the saved follow-up')
        task['issue_ids'] = list(dict.fromkeys([*task.get('issue_ids', []), key]))
        self._dev_save(s, fx, 'bot_tasks', task)
        return copy.deepcopy(issue)

    def _issue_view(self, s, actor, issue, state):
        result = copy.deepcopy(issue); manifest = self._manifest(s, state['snapshot'])
        resolution = issue.get('resolution'); changed = []; reasons = []
        if resolution:
            changed = [p for p,h in resolution['hashes'].items() if manifest.get(p, {}).get('hash') != h]
            if changed: reasons.append('evaluated_files_changed')
            if any(ref not in state['context'].get('requirement_refs', []) for ref in issue['requirement_refs']):
                reasons.append('requirement_mapping_changed')
            if stale_refs(s, issue['requirement_refs']): reasons.append('requirement_revision_changed')
            if digest(_premises(state['context'])) != resolution['premises']: reasons.append('context_changed')
            from .design_assessment import map_fingerprint
            if 'validation_maps' not in resolution or map_fingerprint(self, s, [state['id']]) != resolution['validation_maps']:
                reasons.append('validation_maps_changed_or_unrecorded')
            checks = {c['id']: c for c in assess(state['context'], manifest)['checks']}
            if any(checks.get(c['id'], {}).get('effective_status') != 'pass' or
                   digest(checks.get(c['id'])) != resolution['checks'].get(c['id']) for c in issue['checks']):
                reasons.append('verification_changed_or_missing')
        result.update(effective_status='needs_recheck' if issue['status'] == 'resolved' and reasons else issue['status'],
            applicable_state=state['id'], changed_paths=changed, recheck_reasons=reasons,
            formal_adoption=False, product_complete=False,
            requirement_link_status='linked' if issue['requirement_refs'] else 'unlinked',
            limitation='Bot judgment and submitted, version-bound tool evidence; not independent physical certification.')
        return result

    def cmd_get_bot_issue(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        self._bd_project(s, actor, task['session_id'], active=False)
        issue = self._dev_get(s, 'bot_issues', a['issue_id'])
        require(issue['session_id'] == task['session_id'], 'scope_denied', 'Issue belongs to another project')
        self._issue_access(s, actor, issue)
        state = self._issue_state(s, actor, task, a.get('state_id', task.get('output_state', task['state_id'])))
        limit = a.get('limit', 30)
        seq, ident = 0, ''
        if a.get('after'):
            try: number, ident = a['after'].split(':', 1); seq = int(number)
            except ValueError: require(False, 'invalid_input', 'Invalid history cursor')
            require(seq >= 0 and ident, 'invalid_input', 'Invalid history cursor')
        rows = con.execute('SELECT id,created_seq FROM records WHERE collection=? AND subject_id=? '
            'AND (created_seq>? OR (created_seq=? AND id>?)) ORDER BY created_seq,id LIMIT ?',
            ('bot_issue_events', issue['id'], seq, seq, ident, limit+1)).fetchall()
        history = []
        for row in rows[:limit]:
            event = s['bot_issue_events'][row[0]]
            for ident in [event.get('state_id'), event.get('previous', {}).get('baseline_state'),
                          (event.get('resolution') or {}).get('state_id')]:
                if ident: self._continuity_state(s, actor, ident)
            history.append(copy.deepcopy(event))
        return {'issue': self._issue_view(s, actor, issue, state),
            'history': history,
            'next_cursor': str(rows[limit-1][1])+':'+rows[limit-1][0] if len(rows)>limit else None}

    def _issue_context(self, s, actor, task, con):
        """Linked work first; bounded summaries, full declarations fetched on demand."""
        owned = con.execute('SELECT id FROM records WHERE collection=? AND session_id=? AND subject_id=? ORDER BY id LIMIT 21',
            ('bot_issues', task['session_id'], task['bot_id'])).fetchall()
        ids = list(dict.fromkeys([*task.get('issue_ids', []), *(r[0] for r in owned[:20])]))
        state = self._issue_state(s, actor, task, task.get('output_state', task['state_id']))
        items = []
        for ident in ids:
            if not self._issue_readable(s, actor, s['bot_issues'][ident]): continue
            row = self._issue_view(s, actor, s['bot_issues'][ident], state)
            summary = {k: row[k] for k in ('id','owner_bot_id','status','effective_status','version','applicable_state',
                'formal_adoption','product_complete','requirement_link_status')}
            summary.update(summary=row['summary'][:500], paths=row['paths'][:10],
                completion=[text[:300] for text in row['completion'][:5]],
                requirement_refs=row['requirement_refs'][:10], recheck_reasons=row['recheck_reasons'],
                check_ids=[c['id'] for c in row['checks']], detail_operation='get_bot_issue', detail_is_summary=True)
            if row.get('resolution'): summary['resolution_state'] = row['resolution']['state_id']
            items.append(summary)
        total = len(items)
        while len(json.dumps(items).encode()) > 64000: items.pop()
        return {'items': items, 'scope':'linked issues and first 20 owned issues',
            'owned_truncated': len(owned)>20, 'context_truncated':len(items)<total,
            'retrieval':'list_bot_issues / get_bot_issue'}

    def cmd_list_bot_issues(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        self._bd_project(s, actor, task['session_id'], active=False)
        state = self._issue_state(s, actor, task, a.get('state_id', task.get('output_state', task['state_id'])))
        limit = a.get('limit', 30)
        rows = con.execute('SELECT id FROM records WHERE collection=? AND session_id=? AND id>? ORDER BY id LIMIT ?',
            ('bot_issues', task['session_id'], a.get('after', ''), limit+1)).fetchall()
        return {'items': [self._issue_view(s, actor, s['bot_issues'][r[0]], state) for r in rows[:limit]
                         if self._issue_readable(s, actor, s['bot_issues'][r[0]])],
            'next_cursor': rows[limit-1][0] if len(rows)>limit else None}

    def cmd_review_bot_issue(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        issue = self._dev_get(s, 'bot_issues', a['issue_id'])
        require(issue['session_id'] == task['session_id'], 'scope_denied', 'Issue belongs to another project')
        self._issue_access(s, actor, issue)
        self._issue_authority(s, actor, task, issue['owner_bot_id'])
        require(issue['id'] in task.get('issue_ids', []), 'scope_denied', 'Act through an issue-linked assignment')
        require(all(in_scope(p, task['write_scope']) for p in issue['paths']),
                'scope_denied', 'Disposition exceeds this assignment scope')
        require(a['version'] == issue['version'], 'stale_basis', 'Issue changed; reread before deciding')
        require(a['reason'].strip() and a['evidence'], 'evidence_required', 'Reason and saved evidence required')
        self._bd_evidence(s, actor, task['session_id'], a['evidence'])
        state = self._issue_state(s, actor, task, a['state_id'])
        reassessment = a.get('reassessment')
        if reassessment is not None:
            require(a['status'] == 'reopened' and state['id'] == task.get('output_state', task['state_id']),
                    'invalid_input', 'Reassess explicitly at this task state while reopening')
            refs = reassessment['requirement_refs']
            require({r['requirement_id'] for r in issue['requirement_refs']} <= {r['requirement_id'] for r in refs},
                    'invalid_input', 'Reassessment cannot drop issue requirements')
            _subset_refs(task.get('requirement_refs', []), refs)
            require(not stale_refs(s, refs), 'stale_basis', 'Use current adopted requirement revisions')
            plan, checks = self._issue_plan(s, state, reassessment['verification_plan'], reassessment['check_ids'], issue['paths'], refs)
            previous = {k:copy.deepcopy(issue[k]) for k in ('requirement_refs','verification_plan','checks','baseline_state')}
            issue.update(requirement_refs=copy.deepcopy(refs), verification_plan=plan, checks=checks, baseline_state=state['id'])
            self._issue_event(s, fx, issue, task, 'reassessment', previous=previous,
                replacement={k:copy.deepcopy(issue[k]) for k in previous}, reason=a['reason'], state_id=state['id'])
        if a['status'] == 'resolved':
            require(issue['status'] != 'resolved', 'invalid_state', 'Reopen before replacing a resolution')
            proof = self._issue_resolution(s, actor, task, issue, state, a.get('verification_task_ids', []), con)
            issue['resolution'] = dict(proof, state_id=state['id'], reason=a['reason'], evidence=copy.deepcopy(a['evidence']),
                task_id=task['id'], bot_id=task['bot_id'], principal_id=actor['id'], at=self.clock())
        else:
            require(not a.get('verification_task_ids'), 'invalid_input', 'Verification task references are for resolution')
            require(issue['status'] != 'resolved' or a['status'] == 'reopened', 'invalid_state', 'Explicit reopening required')
            if a['status'] == 'reopened': issue['cycle_started_seq'] = s['seq']+1
        issue.update(status=a['status'], version=issue['version']+1)
        self._dev_save(s, fx, 'bot_issues', issue)
        self._issue_event(s, fx, issue, task, a['status'], state_id=state['id'], reason=a['reason'],
            evidence=copy.deepcopy(a['evidence']), resolution=copy.deepcopy(issue.get('resolution')) if a['status']=='resolved' else None)
        return copy.deepcopy(issue)

    def _issue_resolution(self, s, actor, task, issue, state, verification_ids, con):
        require(verification_ids and len(set(verification_ids)) == len(verification_ids),
                'evidence_required', 'Completed linked verification required')
        require(not stale_refs(s, issue['requirement_refs']), 'stale_basis', 'Issue requirements changed; reassessment required')
        _subset_refs(state['context'].get('requirement_refs', []), issue['requirement_refs'])
        manifest = self._manifest(s, state['snapshot'])
        plan = issue['verification_plan']
        require(manifest.get(plan['path'], {}).get('hash') == plan['sha256'], 'stale_basis', 'Acceptance plan changed')
        checks = {c['id']: c for c in assess(state['context'], manifest)['checks']}
        pins = {plan['path']: plan['sha256']}
        for declaration in issue['checks']:
            check = checks.get(declaration['id'], {})
            require(check.get('effective_status') == 'pass' and check.get('physical_plan') == plan,
                    'evidence_required', 'Required check has no applicable bound pass', check_id=declaration['id'])
            require(set(declaration['inputs']) <= set(check.get('inputs', {})),
                    'evidence_required', 'Check omitted declared inputs')
            require(check.get('evidence', {}).get(declaration['report']) == manifest.get(declaration['report'], {}).get('hash')
                    and declaration['report'] in check.get('evidence', {}), 'evidence_required', 'Bound report evidence required')
            physical = check.get('physical_result', {})
            execution = physical.get('execution', {})
            require(execution.get('exit_code') == 0 and execution.get('action_key') and physical.get('status') == 'pass',
                    'evidence_required', 'Executed adapter evidence required')
            require(all(check.get(k) == declaration.get(k, []) for k in ('scope', 'components', 'required', 'requirement_refs')),
                    'evidence_required', 'Check definition differs from issue acceptance')
            pins.update(check['inputs']); pins.update(check['evidence'])
        verified = []
        for ident in verification_ids:
            other = self._dev_get(s, 'bot_tasks', ident)
            require(other['session_id'] == task['session_id'] and issue['id'] in other.get('issue_ids', [])
                    and other['kind'] == 'verify' and other['status'] == 'completed' and other['reports']
                    and other['reports'][-1]['seq'] > issue['cycle_started_seq'],
                    'evidence_required', 'Verification must be linked, completed and from this issue cycle')
            output = s['dev_states'][other['reports'][-1]['state_id']]
            require(output['id'] == state['id'], 'evidence_required', 'Resolve the exact verification output state')
            _subset_refs(other.get('requirement_refs', []), issue['requirement_refs'])
            require(not stale_refs(s, other.get('requirement_refs', [])), 'stale_basis', 'Verification requirements changed')
            verified.append(ident)
        # Evidence is authenticated customer-runner reporting, not remote attestation.
        # Re-evaluate saved report bytes against the frozen plan, never a pass label alone.
        from .physical_evidence import evaluate
        for declaration in issue['checks']:
            check = checks[declaration['id']]; path = declaration['report']; info = manifest.get(path)
            require(info and info['size'] <= 1024**2, 'evidence_required', 'Saved bounded report required')
            try: report = json.loads(b''.join(self.store.verified_parts(info)))
            except (ValueError, UnicodeError): require(False, 'evidence_required', 'Malformed report')
            result = evaluate(declaration, report, {p: manifest[p]['hash'] for p in check['inputs'] if p in manifest})
            require(result['status'] == 'pass', 'evidence_required', 'Saved measurements do not satisfy frozen acceptance')
            execution = check['physical_result']['execution']
            found = con.execute('SELECT id FROM records WHERE collection=? AND subject_id IN ('+
                ','.join('?' for _ in verified)+') AND created_seq>?',
                ('bot_actions', *verified, issue['cycle_started_seq'])).fetchall()
            require(any(s['bot_actions'][r[0]]['kind'] == 'tool' and
                s['bot_actions'][r[0]]['input_state'] == execution.get('input_state') and
                s['bot_actions'][r[0]]['details'].get('result', {}).get('output_artifact') == execution.get('output_artifact')
                and s['bot_actions'][r[0]]['details'].get('result', {}).get('exit_code') == 0 for r in found),
                'evidence_required', 'Verification task has no matching tool receipt')
            raw = next(c for c in state['context']['environment']['engineering']['checks'] if c['id'] == declaration['id'])
            def published(row):
                action = s['bot_actions'][row[0]]
                result = action['details'].get('result', {})
                publication = result.get('evidence_publication', {})
                return (action['kind'] == 'tool_evidence' and publication.get('state_id') == state['id']
                    and result.get('exit_code') == 0 and declaration['report'] in result.get('refreshed_paths', [])
                    and any(c == raw and c.get('physical_result', {}).get('execution') == execution
                            for c in publication.get('checks', [])))
            require(any(published(row) for row in found), 'evidence_required',
                    'Exact verification publication and refreshed report receipt required')
        from .design_assessment import map_fingerprint
        return {'verification_task_ids': verified, 'hashes': pins, 'premises': digest(_premises(state['context'])),
            'validation_maps': map_fingerprint(self, s, [state['id']]),
            'checks': {c['id']: digest(checks[c['id']]) for c in issue['checks']}}


def _premises(context):
    result = copy.deepcopy(context)
    engineering = result.get('environment', {}).get('engineering')
    if engineering is not None:
        result['environment']['engineering'] = {k:v for k,v in engineering.items() if k != 'checks'}
    return result
