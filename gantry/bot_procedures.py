"""Versioned Bot preferences over lessons, supported only for recorded conditions.

Peer/tool receipts are attributed executor reports, not execution attestation,
general efficacy, physical certification, or permission to execute lesson text.
"""
import copy

from . import bot_procedure_contracts
from .bot_learning_recall import context_basis
from .model import Fault, digest, require, uid


def basis(s, task):
    return {'state_id':task.get('output_state', task['state_id']),
        'requirement_refs':copy.deepcopy(task.get('requirement_refs', [])),
        'context_basis':context_basis(s, task),
        'environment_hash':s['bot_runtimes'][task['bot_id']]['environment_hash']}


def latest(core, s, memory_id, con):
    row = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? '
        'ORDER BY created_seq DESC,id DESC LIMIT 1', ('bot_procedure_decisions', memory_id)).fetchone()
    return core._dev_get(s, 'bot_procedure_decisions', row[0]) if row else None


def checked(core, s, actor, task, memory, check_id, con, positive=False):
    from .bot_experience_checks import view
    record = core._dev_get(s, 'bot_experience_checks', check_id)
    peer = core._dev_get(s, 'bot_tasks', record['task_id'])
    require(record['subject_id'] == memory['id'] and record['basis']['memory_hash'] == digest(memory),
        'invalid_input', 'Cite a check of this exact lesson')
    visible = view(core, s, actor, peer, con)
    require(visible and visible['available'] and peer.get('experience_check_result') == check_id,
        'stale_basis', 'Procedure check is no longer available')
    if not positive: return []
    pin = record['basis']; current = basis(s, task)
    require(record['status'] == 'completed' and record['verdict'] == 'supported_for_scope',
        'invalid_input', 'Preference requires a completed supporting peer check')
    require(peer['bot_id'] not in {task['bot_id'], memory['bot_id']} and
        peer['principal_id'] not in {actor['id'], memory['principal_id']} and not peer['write_scope'],
        'unauthorized', 'Preference requires an independent read-only peer')
    require(pin['state_id'] == current['state_id'] and pin['requirement_refs'] == current['requirement_refs'] and
        pin.get('requester_context_basis') == current['context_basis'] and
        pin.get('requester_environment_hash') == current['environment_hash'] and
        pin.get('checker_environment_hash') == s['bot_runtimes'][peer['bot_id']]['environment_hash'],
        'stale_basis', 'Procedure check conditions changed or were not captured')
    receipts = []
    for ident in record['action_ids']:
        action = core._dev_get(s, 'bot_actions', ident)
        result = action.get('details', {}).get('result', {})
        if action['kind'] != 'tool' or not isinstance(result, dict): continue
        require(action['task_id'] == peer['id'] and action['principal_id'] == peer['principal_id'] and
            action['attempt'] == peer['attempt'] and action['input_state'] == pin['state_id'] and
            action['created_seq'] <= record['created_seq'], 'invalid_input', 'Tool receipt belongs to another check')
        require(type(result.get('exit_code')) is int and result['exit_code'] == 0 and
            'reason' in result and result['reason'] is None and not result.get('error') and
            result.get('sandbox') in {'macos-seatbelt', 'linux-bubblewrap'} and
            result.get('workspace_changes_applied') == [] and result.get('output_artifact'),
            'invalid_input', 'Cited procedure tool must report a successful read-only sandbox execution')
        details = action['details']
        require(details.get('workspace_before') and details['workspace_before'] == details.get('workspace_after'),
            'invalid_input', 'Procedure tool must preserve the checked workspace')
        core._dev_artifact(s, result['output_artifact'])
        receipts.append(ident)
    require(receipts, 'invalid_input', 'Peer opinion alone is not a procedure test; cite successful tool receipts')
    return receipts


def recalled(core, s, actor, task, memory, con):
    decision = latest(core, s, memory['id'], con)
    if not decision: return None, []
    # Recall adds share_id/presentation fields; evidence pins the saved source.
    memory = core._learning_source(s, actor, task, memory['id'])
    # Sharing a lesson does not expose its author's private check interpretation.
    own = decision['bot_id'] == task['bot_id'] and decision['principal_id'] == actor['id']
    result = copy.deepcopy(decision) if own else {k:decision[k] for k in ('id', 'version', 'status')}
    result['effective_status'] = decision['status']
    if decision['status'] == 'retired': return result, ['procedure_retired']
    if decision['status'] == 'candidate': return result, ['procedure_candidate']
    if not own:
        result['effective_status'] = 'requires_recheck'
        return result, ['procedure_not_tested_for_this_bot']
    flags = []
    if decision['basis'] != basis(s, task): flags.append('procedure_conditions_changed')
    try:
        require(decision['memory_hash'] == digest(memory), 'stale_basis', 'Procedure lesson changed')
        for ident in decision['check_ids']: checked(core, s, actor, task, memory, ident, con, positive=True)
    except Fault:
        flags.append('procedure_evidence_unavailable')
    result['effective_status'] = 'requires_recheck' if flags else 'tested_for_scope'
    result['limits'] = 'Bot preference supported by peer-reported tool receipts for this basis only; no general or physical validation.'
    return result, flags


def decorate(core, s, actor, task, memory, con):
    """Expose dispositions in ordinary context too; full recall owns applicability."""
    result = copy.deepcopy(memory)
    decision, flags = recalled(core, s, actor, task, memory, con)
    if not decision: return result
    result['procedure_decision'] = decision
    result['applicability_flags'] = list(dict.fromkeys([*result.get('applicability_flags', []), *flags]))
    result['allowed_uses'] = (['reject'] if decision['status'] == 'retired' else
        ['recheck', 'reject'] if flags else result.get('allowed_uses', ['recheck', 'reject']))
    return result


class BotProcedureMixin:
    def cmd_record_bot_procedure_decision(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        require(task.get('studio_mode') != 'ask' and not task.get('reply_request_id'),
            'scope_denied', 'Read-only consultation cannot select enduring procedure preferences')
        memory = self._learning_source(s, actor, task, a['memory_id'])
        require(memory.get('bot_id') == task['bot_id'] and memory['principal_id'] == actor['id'],
            'unauthorized', 'Only the lesson author can select its enduring procedure preference')
        lesson = memory.get('lesson', {})
        require(lesson.get('kind') == 'procedure' and lesson.get('when_to_use', '').strip() and
            lesson.get('when_not_to_use') and any(v.strip() for v in lesson['when_not_to_use']) and
            lesson.get('procedure_steps') and
            all(step.strip() for step in lesson['procedure_steps']),
            'invalid_input', 'Refine experience into a conditional lesson with ordered procedure_steps first')
        previous = latest(self, s, memory['id'], con)
        require(a['version'] == (previous or {}).get('version', 0), 'stale_basis', 'Procedure decision changed')
        require(a['reason'].strip() and len(set(a['check_ids'])) == len(a['check_ids']),
            'invalid_input', 'Give a reason and distinct check IDs')
        require(a['status'] != 'preferred' or a['check_ids'], 'invalid_input',
            'Self-assessment and reported helpfulness cannot establish a tested procedure')
        receipts = []
        for ident in a['check_ids']:
            receipts.extend(checked(self, s, actor, task, memory, ident, con, positive=a['status'] == 'preferred'))
        record = dict({k:copy.deepcopy(v) for k,v in a.items() if k != 'fence'},
            id=uid('bprocedure'), subject_id=memory['id'], session_id=task['session_id'], bot_id=task['bot_id'],
            principal_id=actor['id'], version=a['version']+1, memory_hash=digest(memory), basis=basis(s, task),
            previous_id=previous['id'] if previous else None, tool_action_ids=sorted(set(receipts)),
            evidence_status='peer_report_with_successful_tool_receipts' if receipts else 'bot_judgment',
            formal_adoption=False, created_seq=s['seq']+1)
        return self._dev_save(s, fx, 'bot_procedure_decisions', record)
