"""Small native-data views. Source bytes remain independently retrievable."""
import copy
from . import manifest_store
from .contracts import register, S, O, A, I
from .model import require, uid, canonical

SOURCE = {'type': 'object', 'properties': {'revision_id': S, 'path': S, 'sha256': S,
    'locator': S}, 'required': ['revision_id', 'path', 'sha256', 'locator'], 'additionalProperties': False}
FIELD = {'type': 'object', 'properties': {'name': S, 'value': {}, 'unit': S, 'frame': S,
    'time_basis': S, 'classification': {'enum': ['observed', 'declared', 'derived', 'unknown']},
    'source_index': {'type': 'integer', 'minimum': 0}, 'method': S},
    'required': ['name', 'value', 'classification', 'source_index', 'method'], 'additionalProperties': False}
register('record_evidence_view', {'state_id': S, 'subject_id': S, 'profile': S,
    'extractor': S, 'sources': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': SOURCE},
    'fields': {'type': 'array', 'maxItems': 200, 'items': FIELD}, 'missing': A,
    'extensions': O, 'execution_id': S, 'change_id': S},
    ['state_id', 'subject_id', 'profile', 'extractor', 'sources', 'fields', 'missing'])
register('get_evidence_view', {'view_id': S, 'fields': A}, ['view_id'])
OUTPUT_FIELD = {'type': 'object', 'properties': {'source': S, 'target': S, 'unit': S,
    'frame': S, 'time_basis': S}, 'required': ['source', 'target'], 'additionalProperties': False}
OUTPUT_PROFILE = {'type': 'object', 'properties': {'id': S, 'version': I,
    'fields': {'type': 'array', 'minItems': 1, 'maxItems': 200, 'items': OUTPUT_FIELD}},
    'required': ['id', 'version', 'fields'], 'additionalProperties': False}
register('render_evidence_view', {'view_id': S, 'state_id': S, 'profile': OUTPUT_PROFILE},
    ['view_id', 'state_id', 'profile'])
register('query_evidence', {'state_id': S, 'subject_id': S, 'profile': S, 'after': S,
    'as_of_seq': {'type': 'integer', 'minimum': 0},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['state_id'])


class EvidenceMixin:
    def cmd_record_evidence_view(self, s, actor, a, fx, n, con):
        self.allowed(actor, 'record')
        state = self._dev_get(s, 'dev_states', a['state_id'])
        session = self._dev_session(s, actor, state['session_id'])
        require(any(x['id'] == a['subject_id'] for x in state['hierarchy']),
                'invalid_input', 'Subject must be a stable hierarchy ID')
        for source in a['sources']:
            artifact = self._dev_artifact(s, source['revision_id'])
            self.zone_write(actor, artifact['zone'])
            info = artifact['data']['files'].get(source['path'])
            require(info and info['hash'] == source['sha256'], 'stale_basis', 'Source file/hash mismatch')
        for field in a['fields']:
            require(field['source_index'] < len(a['sources']), 'invalid_input', 'Unknown source index')
            require(field['classification'] != 'unknown' or field['value'] is None,
                    'invalid_input', 'Unknown values must be null, not inferred zero')
        require(len({f['name'] for f in a['fields']}) == len(a['fields']), 'invalid_input', 'Duplicate field name')
        for key, table in [('execution_id', 'dev_executions'), ('change_id', 'dev_changes')]:
            if key in a:
                obj = self._dev_get(s, table, a[key])
                require(obj['session_id'] == session['id'], 'invalid_input', 'Cross-session reference')
                if key == 'execution_id':
                    require(obj.get('input_state') == state['id'], 'stale_basis', 'Execution used another state')
        require(len(canonical(a).encode()) <= 262144, 'invalid_input', 'View exceeds 256 KiB')
        view = {k: copy.deepcopy(v) for k, v in a.items() if k not in {'basis', 'intent'}}
        view.update(id=uid('view'), session_id=session['id'], schema_version=1,
                    created_seq=s['seq'] + 1, actor_id=actor['id'], adoption='unadopted')
        self._put(s, fx, 'evidence_views', view['id'], view)
        return view

    def cmd_get_evidence_view(self, s, actor, a, fx, n, con):
        view = self._dev_get(s, 'evidence_views', a['view_id'])
        self._dev_session(s, actor, view['session_id'])
        if 'fields' in a:
            selected = set(a['fields']); names = {f['name'] for f in view['fields']}
            require(selected <= names, 'not_found', 'Requested field is not in view')
            view['omitted_fields'] = sorted(names - selected)
            view['fields'] = [f for f in view['fields'] if f['name'] in selected]
        view['guarantee'] = 'Source identity verified; submitted extraction semantics are not automatically certified'
        return view

    def cmd_query_evidence(self, s, actor, a, fx, n, con):
        state = self._dev_get(s, 'dev_states', a['state_id'])
        self._dev_session(s, actor, state['session_id'])
        seq = a.get('as_of_seq', s['seq']); require(seq <= s['seq'], 'invalid_input', 'Future query sequence')
        where = ['collection=?', 'state_id=?', 'created_seq<=?', 'id>?']
        params = ['evidence_views', state['id'], seq, a.get('after', '')]
        for key in ('subject_id', 'profile'):
            if key in a: where.append(key + '=?'); params.append(a[key])
        limit = a.get('limit', 25)
        import json
        rows = [manifest_store.unpack(con,json.loads(row[0])) for row in con.execute(
            'SELECT body FROM records WHERE ' + ' AND '.join(where) + ' ORDER BY id LIMIT ?', params + [limit + 1])]
        return {'items': [{k: v[k] for k in ('id', 'subject_id', 'profile', 'created_seq', 'missing')}
                          for v in rows[:limit]], 'as_of_seq': seq,
                'next': rows[limit-1]['id'] if len(rows) > limit else None}

    def cmd_render_evidence_view(self, s, actor, a, fx, n, con):
        view = self.cmd_get_evidence_view(s, actor, {'view_id': a['view_id']}, fx, n, con)
        require(view['state_id'] == a['state_id'], 'stale_basis', 'View describes another development state')
        for source in view['sources']:
            artifact = self._dev_artifact(s, source['revision_id'])
            require(artifact['data']['files'].get(source['path'], {}).get('hash') == source['sha256'],
                    'stale_basis', 'View source no longer available')
        from .tool_views import render
        return render(view, a['profile'])
