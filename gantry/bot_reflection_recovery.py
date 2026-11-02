"""Isolate a failed reflection; never retry an uncertain model request implicitly."""
import json
import shutil
from pathlib import Path

from .model import Fault, require, uid
from .runner import persist

HELD_CODES = {'provider_failed', 'provider_rate_limited', 'provider_timeout', 'outcome_unknown', 'context_limit', 'invalid_input'}


def attempt_reflection(client, item, infer, root):
    from .bot_learning_runtime import reflect
    directory = Path(root)/item['id']
    held = directory/'held.json'
    if held.exists():
        # Recheck access even to a saved failure. No model call while held.
        current = client.call('get_bot_reflection', {'reflection_id': item['id']})
        if current['status'] == 'completed': return current
        return json.loads(held.read_text())
    try: return reflect(client, item, infer, root)
    except (Fault, OSError, ValueError) as exc:
        if isinstance(exc, Fault) and exc.code not in HELD_CODES: raise
        result = {'reflection_id': item['id'], 'status': 'held',
                  'reason': exc.code if isinstance(exc, Fault) else type(exc).__name__,
                  'next_action': 'Inspect private journal; explicit recover-reflection is required'}
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        persist(held, result)
        return result


def recover_reflection(client, bot_id, reflection_id, infer, root, reason, retry_inference=False):
    require(isinstance(reason, str) and bool(reason.strip()), 'invalid_input', 'Confirm previous processes stopped')
    item = client.call('get_bot_reflection', {'reflection_id': reflection_id})
    require(item['bot_id'] == bot_id, 'scope_denied', 'Use this Bot reflection journal')
    if item['status'] == 'completed': return item
    directory = Path(root)/item['id']; marker = directory/'reflection.json'
    require(marker.is_file(), 'not_found', 'Original private reflection journal required')
    saved = json.loads(marker.read_text())
    receipt = directory/'inference'/'receipt.json'
    provider = directory/'inference'/'model'/'inference.json'
    from .monthly_recovery import ensure_stopped, prepare_retry
    provider_state = json.loads(provider.read_text()) if provider.is_file() else None
    if provider_state: ensure_stopped(provider_state)
    known = ('receipt' in saved or receipt.is_file() or
             provider.is_file() and json.loads(provider.read_text()).get('phase') == 'completed')
    require(known or retry_inference, 'outcome_unknown', 'No complete receipt; explicitly choose a new inference attempt')
    monthly_retry = False
    if retry_inference and provider_state and provider_state.get('phase') != 'completed':
        prepare_retry(provider.parent, reason)
        monthly_retry = True
    archive = directory/'recoveries'/uid('recovery'); archive.mkdir(parents=True, mode=0o700)
    persist(archive/'recovery.json', {'reason': reason, 'retry_inference': retry_inference})
    shutil.copy2(marker, archive/'reflection.json')
    # A new inference is explicit, including an invalid earlier structured answer.
    # Without this flag, reconcile a known receipt instead of spending again.
    if retry_inference and not monthly_retry:
        if (directory/'inference').exists(): (directory/'inference').rename(archive/'inference')
        if saved.get('validation_error') and saved.get('receipt'):
            saved['input'] = {**saved['input'], 'previous_submission': saved['receipt']['output'],
                'validation_feedback': saved.pop('validation_error'),
                'correction_instruction': 'Correct the rejected structured submission using the saved evidence. '
                    'Feedback may cite only unique memory IDs marked apply or recheck in plan.output.decisions. '
                    'Do not weaken requirements or invent evidence to satisfy validation.'}
        saved.pop('receipt', None); saved.pop('result', None); persist(marker, saved)
    if (directory/'held.json').exists(): (directory/'held.json').rename(archive/'held.json')
    return attempt_reflection(client, item, infer, root)
