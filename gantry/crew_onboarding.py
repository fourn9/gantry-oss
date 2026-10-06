"""Inferred organizations are proposals; owner activation is one transaction."""
import copy

from .contracts import register, S, A
from .model import require, uid, digest
from .review_contracts import BOT_PROFILE

MEMBER = {'type': 'object', 'properties': {
    'bot_id': S, 'name': S, 'parent_bot_id': {'type': ['string', 'null']}, 'principal_id': S,
    'profile': BOT_PROFILE, 'write_scope': A, 'can_assign': {'type': 'boolean'}, 'can_integrate': {'type': 'boolean'}},
    'required': ['bot_id', 'name', 'parent_bot_id', 'principal_id', 'profile', 'write_scope', 'can_assign', 'can_integrate'],
    'additionalProperties': False}
TEAM = {'session_id': S, 'organization_id': S, 'lead_bot_id': S, 'goal': S, 'acceptance': A,
        'members': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': MEMBER}, 'rationale': S}
register('propose_bot_team', {**TEAM, 'task_id': S, 'fence': S}, list(TEAM))
register('get_bot_team_proposal activate_bot_team', {'proposal_id': S}, ['proposal_id'])


class CrewOnboardingMixin:
    def cmd_propose_bot_team(self, s, actor, a, fx, n, con):
        d = self._dev_session(s, actor, a['session_id']); self.allowed(actor, 'record')
        require(('task_id' in a) == ('fence' in a), 'invalid_input', 'Supply both task identity fields')
        if 'task_id' in a:
            task = self._bd_checked(s, actor, a, con)
            require(task['session_id'] == d['id'], 'scope_denied', 'Team proposal belongs to another project')
        org = self._dev_get(s, 'organizations', a['organization_id'])
        require(org['owner'] == d['owner'], 'scope_denied', 'Organization and project owner must match')
        members = {m['bot_id']: m for m in a['members']}
        require(len(members) == len(a['members']) and a['lead_bot_id'] in members, 'invalid_input', 'Unique Bots and a lead required')
        require(members[a['lead_bot_id']]['parent_bot_id'] is None, 'invalid_input', 'Lead must be the root')
        require(len({m['principal_id'] for m in members.values()}) == len(members), 'invalid_input', 'Each Bot needs its own principal')
        for member in members.values():
            seen = set(); current = member['bot_id']
            while current:
                require(current in members and current not in seen, 'invalid_input', 'Hierarchy must be acyclic and complete')
                seen.add(current); current = members[current]['parent_bot_id']
            require(a['lead_bot_id'] in seen, 'invalid_input', 'Every Bot must report to the lead')
        versions = self._crew_team_versions(s, d, org, members)
        return self._dev_save(s, fx, 'bot_team_proposals', dict(id=uid('bteam'), subject_id=d['id'],
            session_id=d['id'], organization_id=org['id'], configuration={k: copy.deepcopy(a[k]) for k in TEAM}, source_task=a.get('task_id'), input_versions=versions,
            status='proposed', author=actor['id'], created_seq=s['seq'] + 1))

    def _crew_team_versions(self, s, d, org, members):
        return {'session': d['version'], 'organization': org['version'],
            'project': s.get('bot_projects', {}).get(d['id'], {}).get('version', 0),
            'bots': {bid: s.get('persistent_bots', {}).get(bid, {}).get('version', 0) for bid in members},
            'bindings': {bid: s.get('bot_bindings', {}).get(digest([d['id'], 'development:'+bid]), {}).get('version', 0) for bid in members}}

    def cmd_get_bot_team_proposal(self, s, actor, a, fx, n, con):
        proposal = self._dev_get(s, 'bot_team_proposals', a['proposal_id'])
        self._dev_session(s, actor, proposal['session_id']); return proposal

    def cmd_activate_bot_team(self, s, actor, a, fx, n, con):
        proposal = self.cmd_get_bot_team_proposal(s, actor, a, fx, n, con)
        d = self._dev_session(s, actor, proposal['session_id']); self._dev_human(actor, d)
        config = proposal['configuration']; org = self._organization_owner(s, actor, config['organization_id'])
        require(proposal['status'] == 'proposed', 'invalid_state', 'Team proposal already handled')
        members = {m['bot_id']: m for m in config['members']}; versions = proposal['input_versions']
        require(versions == self._crew_team_versions(s, d, org, members), 'stale_basis', 'Organization changed after proposal')
        pending = dict(members); configured = set()
        while pending:
            ready = [m for m in pending.values() if m['parent_bot_id'] is None or m['parent_bot_id'] in configured]
            require(ready, 'invalid_input', 'Invalid organization graph')
            for member in ready:
                bid = member['bot_id']
                self.cmd_configure_bot(s, actor, {k: member[k] for k in ('bot_id', 'name', 'parent_bot_id', 'profile')} |
                    {'organization_id': org['id'], 'version': versions['bots'][bid], 'enabled': True}, fx, n, con)
                configured.add(bid); del pending[bid]
        self.cmd_configure_bot_project(s, actor, {k: config[k] for k in ('session_id', 'organization_id', 'lead_bot_id', 'goal', 'acceptance')} |
            {'version': versions['project'], 'enabled': True}, fx, n, con)
        for bid, member in members.items():
            self.cmd_bind_development_bot(s, actor, {k: member[k] for k in ('bot_id', 'principal_id', 'write_scope', 'can_assign', 'can_integrate')} |
                {'session_id': d['id'], 'version': versions['bindings'][bid], 'enabled': True}, fx, n, con)
        # No old Bot is deleted or silently removed from an organization.
        proposal.update(status='activated', activated_by=actor['id'], activated_seq=s['seq'] + 1)
        return self._dev_save(s, fx, 'bot_team_proposals', proposal)
