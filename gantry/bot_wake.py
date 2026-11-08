"""Selective reassessment under explicit standing authority; no solution selection."""
import copy
from .development import in_scope
from .model import Fault, digest, require
from .bot_development import TERMINAL


def task_signal(task):
    return [task['status'] if task['status'] in TERMINAL else 'unfinished',
            task['reports'][-1]['seq'] if task['reports'] else None]


class BotWakeMixin:
    def _continuation_basis(self, s, policy):
        sid, bid = policy['session_id'], policy['bot_id']
        b = self._bd_binding(s, sid, bid); bot, org = self._persistent_identity(s, bid)
        project = self._dev_get(s, 'bot_projects', sid); session = self._dev_get(s, 'dev_sessions', sid)
        return {'binding':b['version'], 'bot':bot['version'], 'organization':org['version'],
                'project':project['version'], 'delegation':digest({k:session.get(k) for k in
                 ('mode','actors','write_scope','recipes','max_executions','timeout_seconds','max_parallel')})}

    def _continuation_integrity(self, s, policy):
        require(policy['enabled'] and policy['basis']==self._continuation_basis(s, policy),
                'stale_basis', 'Standing responsibility disabled or changed; owner must reassess')
        # Check the original delegator without impersonating it for execution.
        principal = s['principals'].get(policy['principal_id'])
        require(principal and principal.get('enabled', True) and
                (principal.get('expires_at') is None or self.clock() < principal['expires_at']),
                'unauthorized', 'Standing executor is revoked or expired')
        b, _, _, d = self._bd_actor(s, principal, policy['session_id'], policy['bot_id'])
        require(d['mode']=='execute',
                'unauthorized', 'Standing delegation belongs to this executor in execute mode')
        require(all(in_scope(p,b['write_scope']) and in_scope(p,d['write_scope']) for p in policy['write_scope']),
                'scope_denied', 'Standing scope exceeds current delegation')

    def _continuation_valid(self, s, actor, policy):
        require(policy['principal_id']==actor['id'], 'unauthorized', 'Standing delegation belongs to another executor')
        self._continuation_integrity(s, policy)

    @staticmethod
    def _inherit_continuation(source, target):
        if source.get('continuation_id'):
            target.update(continuation_id=source['continuation_id'], continuation_version=source['continuation_version'])

    def _check_continuation_task(self, s, actor, task):
        if task.get('continuation_id'):
            policy = self._dev_get(s, 'bot_continuations', task['continuation_id'])
            require(policy['version']==task['continuation_version'], 'stale_basis', 'Standing responsibility changed')
            self._continuation_integrity(s, policy)

    def cmd_configure_bot_continuation(self, s, actor, a, fx, n, con):
        project, d = self._bd_project(s, actor, a['session_id'], active=False)
        self._dev_human(actor, d)
        require(self._bd_owner(actor, project), 'unauthorized', 'Project owner required')
        b = self._bd_binding(s, d['id'], a['bot_id'])
        self._dev_paths(a['write_scope'], True); self._dev_paths(a['dependencies'])
        require(all(in_scope(p,b['write_scope']) and in_scope(p,d['write_scope']) for p in a['write_scope']),
                'scope_denied', 'Standing scope exceeds binding')
        manifest = self._manifest(s, s['dev_states'][d['active_state']]['snapshot'])
        require(set(a['dependencies']) <= set(manifest), 'invalid_input', 'Use saved dependency paths')
        key = digest([d['id'], a['bot_id']]); old = s.get('bot_continuations',{}).get(key, {})
        require(a['version']==old.get('version',0), 'stale_basis', 'Standing delegation changed')
        policy = dict(copy.deepcopy(a), id=key, subject_id=a['bot_id'], principal_id=b['principal_id'],
            version=a['version']+1, created_seq=s['seq']+1, last_signal=None,
            last_task_id=old.get('last_task_id'))
        policy['basis'] = self._continuation_basis(s, policy)
        return self._dev_save(s, fx, 'bot_continuations', policy)

    def _continuation_signal(self, s, policy, note):
        session = s['dev_sessions'][policy['session_id']]
        manifest = self._manifest(s, s['dev_states'][session['active_state']]['snapshot'])
        baseline = note['watch_basis']; content = note['content']
        paths = {p:manifest.get(p,{}).get('hash') for p in content['watch_paths']}
        tasks = {tid:task_signal(self._dev_get(s,'bot_tasks',tid)) for tid in content['watch_tasks']}
        due = content['due_at']; reached = due is not None and self.clock()>=due
        reasons = []
        if paths != baseline['paths']: reasons.append('watched_path_changed')
        if tasks != baseline['tasks']: reasons.append('watched_task_changed')
        if reached: reasons.append('due')
        return reasons, digest({'paths':paths,'tasks':tasks,'due_at':due if reached else None}), session

    def _poll_continuation(self, s, actor, policy, fx, n, con):
        self._continuation_valid(s, actor, policy)
        note = self._working_note(s, policy['session_id'], policy['bot_id'])
        if not note: return {'status':'idle','continuation_id':policy['id']}
        require(note['principal_id']==actor['id'], 'unauthorized', 'Working note belongs to a previous executor')
        # Do not overlap any existing work for this Bot/project. In particular,
        # held work may have uncertain external effects and must not be replaced.
        rows = con.execute("SELECT id FROM records WHERE collection='bot_tasks' AND subject_id=? AND session_id=? "
            "AND COALESCE(json_extract(body,'$.value.status'),json_extract(body,'$.status')) "
            "IN ('pending','running','waiting','held') LIMIT 1", (policy['bot_id'],policy['session_id']))
        active = rows.fetchone()
        if active: return {'status':'active','continuation_id':policy['id'],'task_id':active[0]}
        reasons, signal, session = self._continuation_signal(s, policy, note)
        if not reasons or signal==policy.get('last_signal'):
            return {'status':'idle','continuation_id':policy['id']}
        # Carry explicit watched work, not every project issue. Ownership and
        # engineering disposition remain the Bot's decision under its scope.
        issue_ids = list(dict.fromkeys(ident for tid in note['content']['watch_tasks']
            for ident in s['bot_tasks'][tid].get('issue_ids', [])))
        issue_ids = [ident for ident in issue_ids if all(in_scope(p, policy['write_scope'])
            for p in s['bot_issues'][ident]['paths'])][:40]
        task = self._bd_assign(s, actor, {'session_id':session['id'], 'bot_id':policy['bot_id'],
            'requested_by_bot':policy['bot_id'], 'state_id':session['active_state'], 'kind':'plan',
            'title':'Reassess standing responsibility',
            'completion':policy['completion'], 'write_scope':policy['write_scope'],
            'dependencies':policy['dependencies'], 'after_tasks':[], 'issue_ids':issue_ids}, fx, n, con, standing=policy)
        stored = self._dev_get(s, 'bot_tasks', task['id'])
        stored.update(continuation_id=policy['id'], continuation_version=policy['version'],
                      continuation_reason=reasons, working_note_version=note['version'])
        self._dev_save(s, fx, 'bot_tasks', stored)
        policy.update(last_signal=signal, last_task_id=task['id'])
        self._dev_save(s, fx, 'bot_continuations', policy)
        return {'status':'queued','continuation_id':policy['id'],'task_id':task['id'],'reason':reasons}

    def cmd_poll_bot_continuations(self, s, actor, a, fx, n, con):
        self._runtime_fence(s, actor, a['bot_id'], a['runtime_fence'], con)
        limit=a.get('limit',30)
        rows=con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? AND id>? ORDER BY id LIMIT ?',
            ('bot_continuations',a['bot_id'],a.get('after',''),limit+1)).fetchall()
        items=[]
        for row in rows[:limit]:
            policy=self._dev_get(s,'bot_continuations',row[0])
            if not policy['enabled']: continue
            # Rejections occur before effects; nothing is skipped after assignment.
            try: items.append(self._poll_continuation(s,actor,policy,fx,n,con))
            except Fault as exc: items.append({'status':'blocked','continuation_id':policy['id'],'reason':exc.code})
        return {'items':items, 'next_cursor':rows[limit-1][0] if len(rows)>limit else None}
