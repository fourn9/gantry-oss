"""Hosted workspace product surface; shared by browser, REST, CLI and MCP."""
from .contracts import register, S, I, O, A

register('product_overview', {})
register('project_details', {'project_id': S}, ['project_id'])
register('get_signal', {'signal_id': S}, ['signal_id'])
register('session_details', {'session_id': S, 'state_id': S}, ['session_id'])
register('save_project', {'project_id': S, 'version': I, 'name': S, 'description': S,
    'zone': S, 'baseline_state': S}, ['name', 'description'])
register('configure_integration', {'integration_id': S, 'version': I, 'project_id': S,
    'provider': {'enum': ['github', 'monitoring']}, 'name': S, 'repository': S,
    'credential_ref': S, 'enabled': {'type': 'boolean'}}, ['project_id', 'provider', 'name', 'enabled'])
register('sync_integration', {'integration_id': S}, ['integration_id'])
register('ingest_signal', {'integration_id': S, 'source_event_id': S, 'title': S,
    'body': {'type': 'string'}, 'occurred_at': S, 'unit': S, 'observed_configuration': O,
    'metrics': O, 'artifact_revisions': A}, ['integration_id', 'source_event_id', 'title',
    'body', 'occurred_at', 'observed_configuration'])
register('upload_project_files', {'project_id': S, 'session_id': S, 'summary': S,
    'category': {'enum': ['cad', 'electrical', 'code', 'simulation', 'logs', 'other']},
    'files': {'type': 'object', 'additionalProperties': {'type': 'string'}}},
    ['project_id', 'summary', 'category', 'files'])
register('create_product_session', {'project_id': S, 'title': S, 'goal': S,
    'signal_id': S, 'snapshot': S, 'state_id': S}, ['project_id', 'title', 'goal'])
register('link_product_session', {'project_id': S, 'session_id': S}, ['project_id', 'session_id'])
register('set_session_outcome', {'session_id': S, 'version': I,
    'outcome': {'enum': ['open', 'paused', 'closed']}, 'reason': S},
    ['session_id', 'version', 'outcome', 'reason'])
register('request_mentor', {'session_id': S, 'summary': S}, ['session_id', 'summary'])
register('add_session_note', {'session_id': S, 'body': S}, ['session_id', 'body'])
register('worker_heartbeat', {'worker_id': S, 'kind': {'enum': ['mentor', 'runner', 'analyst']}, 'project_ids': A,
    'session_ids': A, 'status': {'enum': ['idle', 'working', 'error', 'stopped']},
    'summary': S}, ['worker_id', 'kind', 'session_ids', 'status', 'summary'])
