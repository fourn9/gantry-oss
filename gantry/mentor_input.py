"""Loss-explicit inference views. Authoritative Core context/artifacts remain intact."""
import copy
import hashlib
import json
from pathlib import Path

CAD_SUFFIXES = {'.step', '.stp', '.iges', '.igs', '.stl', '.brep'}


def compact_review(context):
    result = copy.deepcopy(context)
    original_pr = context.get('pr_diff', [])

    def signature(diff):
        text = diff.get('text', '')
        lines = text.splitlines(keepends=True)
        if len(lines) >= 2 and lines[0].startswith('--- ') and lines[1].startswith('+++ '):
            text = ''.join(lines[2:])
        return (diff.get('path'), diff.get('before'), diff.get('after'), text)

    pr_signatures = {signature(item) for item in original_pr}

    def compact(diff, duplicate=False):
        if not isinstance(diff, dict) or not isinstance(diff.get('text'), str):
            return
        reason = ('duplicate_pr_diff' if duplicate else
                  'cad_serialization' if Path(diff.get('path', '')).suffix.lower() in CAD_SUFFIXES else None)
        if reason:
            raw = diff.pop('text').encode()
            diff['text_omitted'] = {'reason': reason, 'bytes': len(raw),
                                    'sha256': hashlib.sha256(raw).hexdigest()}

    for item in result.get('pr_diff', []):
        compact(item)
    for key in ('development', 'returned_development'):
        if key in context and 'diffs' in context[key]:
            result[key]['diffs'] = copy.deepcopy(context[key]['diffs'])
        for item in result.get(key, {}).get('diffs', []):
            compact(item, duplicate=signature(item) in pr_signatures)
    # Retrieval inventories are authoritative in Core, not semantic review content.
    def omitted(value, reason):
        raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        return {'reason': reason, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                'count': len(value), 'retrieval': 'Read pinned development state/snapshot from Core'}

    for key in ('development', 'returned_development'):
        dev = result.get(key, {})
        if len(json.dumps(dev.get('manifest', {}))) > 20000:
            dev['manifest_omitted'] = omitted(dev.pop('manifest'), 'artifact_transfer_inventory')
        state = dev.get('state', {})
        for field in ('components', 'changed_paths'):
            if len(json.dumps(state.get(field, []))) > 10000:
                state[field + '_omitted'] = omitted(state.pop(field), 'large_state_inventory')
    # Keep review contract, findings, evidence identities intact; bound diff text explicitly.
    remaining = 100000
    diffs = result.get('pr_diff', []) + result.get('development', {}).get('diffs', []) + result.get('returned_development', {}).get('diffs', [])
    question = result.get('question', '')
    for item in sorted(diffs, key=lambda x: (Path(x.get('path', '')).name not in question, x.get('path', ''))):
        raw = item.get('text')
        if not isinstance(raw, str):
            continue
        size = len(raw.encode())
        if size > 12000 or size > remaining:
            item['text_omitted'] = omitted(item.pop('text'), 'inference_diff_budget')
        else:
            remaining -= size
    result['inference_view'] = {
        'version': 2,
        'scope': 'CAD serialization omitted; inspect native CAD and measured geometry separately. '
                 'Duplicate and over-budget diff text is explicitly omitted; large transfer inventories remain retrievable from pinned Core state. All original bytes remain in Core artifacts.',
    }
    return result


def collect_files(root, max_file=65536, max_total=200000, priority_text=""):
    root = Path(root)
    files, omitted = {}, []
    total = 0
    for path in sorted(root.rglob('*'), key=lambda p: (p.name not in priority_text, p.as_posix())):
        name = path.relative_to(root).as_posix()
        reason = None
        if path.is_symlink():
            reason = 'symlink'
        elif not path.is_file():
            continue
        elif path.suffix.lower() in CAD_SUFFIXES:
            reason = 'cad_serialization'
        elif path.stat().st_size > max_file:
            reason = 'file_text_budget'
        else:
            try:
                text = path.read_text()
                size = len(text.encode())
                if '\x00' in text:
                    reason = 'binary'
                elif total + size > max_total:
                    reason = 'total_text_budget'
                else:
                    files[name] = text
                    total += size
            except (UnicodeError, OSError):
                reason = 'unreadable_as_text'
        if reason:
            omitted.append({'path': name, 'reason': reason})
    return files, {'selected_count': len(files), 'selected_text_bytes': total,
                   'omitted_count': len(omitted), 'omitted': omitted[:100],
                   'omitted_list_truncated': len(omitted) > 100,
                   'meaning': 'This is inference input coverage, not artifact storage coverage.'}
