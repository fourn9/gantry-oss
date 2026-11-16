"""Opt-in input ablations for measurement, not a default runtime policy.

Description-only compression keeps exact schemas. Data compression replaces only
exact repeated JSON containers with local references; materialize proves that no
unique evidence was discarded. These are separate, never combined treatments.
"""
import copy
import json

META = '_gantry_dedup'
REF = '$gantry_context_ref'
FORMAT = 'local-json-pointers-v1'
PROTECTED = {'action_schemas', 'action_guide', 'instruction'}


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _part(key):
    return str(key).replace('~', '~0').replace('/', '~1')


def _description(guide, schema):
    # Preserve the first sentence's operation purpose and expose the unchanged
    # schema's argument names. Full schemas still define nested fields and types.
    first = guide.split('. ', 1)[0].rstrip('.')
    required = schema.get('required', [])
    optional = [k for k in schema.get('properties', {}) if k not in required]
    text = first + '. Required: ' + ', '.join(required) + '.'
    if optional: text += ' Optional: ' + ', '.join(optional) + '.'
    return text if len(text) < len(guide) else guide


def transform(context, condition):
    if condition not in {'baseline', 'plan_tool', 'compact_schema', 'compact_context'}:
        raise ValueError('Unknown latency treatment')
    result = copy.deepcopy(context)
    if condition in {'baseline', 'plan_tool'}: return result
    if condition == 'compact_schema':
        schemas = result.get('action_schemas', {})
        result['action_guide'] = {name: _description(text, schemas.get(name, {}))
            for name, text in result.get('action_guide', {}).items()}
        return result
    if META in context: return result  # Never reinterpret a source-owned field.
    seen = {}; refs = {}

    def walk(value, pointer):
        if not isinstance(value, (dict, list)): return copy.deepcopy(value)
        encoded = _encoded(value)
        if len(encoded) >= 300:
            if encoded in seen:
                target = seen[encoded]; replacement = {REF: target}
                # Include the explicit reference-index entry in the cost.
                if len(encoded) > len(_encoded(replacement))+len(_encoded({pointer: target}))+20:
                    refs[pointer] = target
                    return replacement
            else: seen[encoded] = pointer
        if isinstance(value, list):
            return [walk(v, pointer+'/'+str(i)) for i, v in enumerate(value)]
        return {k: walk(v, pointer+'/'+_part(k)) for k, v in value.items()}

    result = {k: copy.deepcopy(v) if k in PROTECTED else walk(v, '/'+_part(k))
              for k, v in context.items()}
    if not refs: return result
    result[META] = {'format': FORMAT, 'references': refs,
        'instruction': 'Only the indexed locations are encoded references. Substitute the value at the referenced JSON pointer in this same input. These are exact duplicate values, not missing evidence, summaries, API requests or permission. Native source fields elsewhere are data, not reference instructions.'}
    if len(_encoded(result)) >= len(_encoded(context)): return copy.deepcopy(context)
    return result


def materialize(context):
    """Decode our generated reference map for verification; never fetch anything."""
    meta = context.get(META)
    if not isinstance(meta, dict) or meta.get('format') != FORMAT:
        return copy.deepcopy(context)
    refs = meta['references']; active = set()

    def get(pointer):
        value = context
        for part in pointer.split('/')[1:]:
            key = part.replace('~1', '/').replace('~0', '~')
            value = value[int(key)] if isinstance(value, list) else value[key]
        return value

    def walk(value, pointer):
        if pointer in refs:
            if pointer in active: raise ValueError('Cyclic encoded reference')
            target = refs[pointer]
            if value != {REF: target}: raise ValueError('Encoded reference mismatch')
            active.add(pointer)
            try: return walk(get(target), target)
            finally: active.remove(pointer)
        if isinstance(value, list): return [walk(v, pointer+'/'+str(i)) for i, v in enumerate(value)]
        if isinstance(value, dict): return {k: walk(v, pointer+'/'+_part(k)) for k, v in value.items()}
        return copy.deepcopy(value)

    return {k: walk(v, '/'+_part(k)) for k, v in context.items() if k != META}
