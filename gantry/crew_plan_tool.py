"""Experimental plan/tool fusion: one model response, two existing durable actions."""
import copy
import json
from .model import require
from .crew_verification import SCHEMA as PLAN_SCHEMA, plan_verification

GUIDE = 'Same arguments as plan_verification. Explicitly request saving the frozen verification plan and then running its approved tool without another model turn. The tool runs only if the plan is executable and inputs/authority still match; both actions and actual evidence remain separate records.'


def enabled(config): return config.get('experimental_latency') == 'plan_tool'


def model_schema(base, config):
    result = copy.deepcopy(base)
    if enabled(config): result['properties']['action']['enum'].append('plan_and_tool')
    return result


def split(receipt, config):
    if receipt['output']['action'] != 'plan_and_tool': return receipt, None
    require(enabled(config), 'scope_denied', 'Plan/tool experiment is disabled')
    from .contracts import validate
    args = json.loads(receipt['output']['arguments_json']); validate(args, PLAN_SCHEMA)
    receipt = copy.deepcopy(receipt)
    receipt['combined_output'] = copy.deepcopy(receipt['output'])
    receipt['output']['action'] = 'plan_verification'
    return receipt, args


def queue(saved, key):
    args = saved.get('combined_plan')
    if not args or saved['result'].get('status') != 'planned': return None
    return {'plan_args': args, 'plan_result': saved['result'], 'input_state': saved['input_state'],
        'before': saved['before'], 'source_action_key': key,
        'discussion_version': saved['discussion_version'],
        'receipt': {'output': {'action': 'tool', 'arguments_json': json.dumps({'name': args['tool_name']}),
            'rationale': saved['receipt']['output']['rationale']},
            'provider': {'kind': 'planned_tool_continuation', 'source_action_key': key}}}


def resume(client, full, config, workspace, queued, fingerprint):
    require(enabled(config), 'scope_denied', 'Plan/tool experiment disabled during continuation')
    require(full['development']['state']['id'] == queued['input_state'] and
        fingerprint == queued['before'] and full['task']['discussion_version'] == queued['discussion_version'],
        'stale_basis', 'Recorded plan basis changed; queued tool not executed')
    current = plan_verification(client, full, config, queued['plan_args'], workspace)
    require(current == queued['plan_result'] and current['status'] == 'planned',
        'stale_basis', 'Verification contract changed; queued tool not executed')
    return queued['receipt']
