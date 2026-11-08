"""Read-only, bounded navigation of saved JSON evidence; never execute payloads."""
import base64
import binascii
import hashlib
import json
import math
import re
import zlib

from .connection_policy import SECRET
from .contracts import S, validate
from .model import Fault, require
from .project_files import read_file

MAX_DECODED = 64 * 1024 * 1024
ENCODING = 'zlib-base64-json-v1'
_MISSING = object()
INSPECT_JSON_SCHEMA = {'type': 'object', 'properties': {
    'path': S, 'pointer': {'type': 'string', 'maxLength': 4096},
    'nonempty_at': {'type': 'string', 'maxLength': 4096},
    'offset': {'type': 'integer', 'minimum': 0},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 30}},
    'required': ['path'], 'additionalProperties': False}


def pointer_value(context, pointer, missing_ok=False):
    require(not pointer or pointer.startswith('/'), 'invalid_input', 'Use a JSON pointer')
    value = context
    for segment in pointer.split('/')[1:]:
        segment = segment.replace('~1', '/').replace('~0', '~')
        try: value = value[int(segment)] if isinstance(value, list) else value[segment]
        except (KeyError, IndexError, ValueError, TypeError):
            if missing_ok: return _MISSING
            # Only keys from the already-authorized root, never values or input.
            keys = []; remaining = 2048
            if isinstance(context, dict):
                for index, key in enumerate(context):
                    if index >= 32: break
                    size = len(json.dumps(key).encode()) + 2
                    if size <= remaining:
                        keys.append(key); remaining -= size
            raise Fault('not_found', 'Context pointer not found. Inspect the root with pointer ""; '
                        'task reports are at /task/reports when the root contains task. '
                        'Escape ~ as ~0 and / as ~1 inside a key.',
                        {'available_keys': keys, 'keys_omitted': isinstance(context, dict) and len(keys) < len(context)})
    return value


def _json(raw):
    def invalid_constant(_): raise ValueError('Non-JSON constant')
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number): raise ValueError('Nonfinite number')
        return number
    def check_depth(value, depth=0):
        if isinstance(value, (dict, list)):
            require(depth <= 64, 'invalid_input', 'JSON nesting exceeds 64 levels')
            for child in value.values() if isinstance(value, dict) else value:
                check_depth(child, depth+1)
    try:
        value = json.loads(raw, parse_constant=invalid_constant, parse_float=finite_float)
        check_depth(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise Fault('invalid_input', 'Malformed or excessively nested JSON') from None


def _decode(raw):
    value = _json(raw)
    if not isinstance(value, dict) or value.get('encoding') != ENCODING:
        return value, raw, 'json'
    validate(value, {'type': 'object', 'properties': {
        'encoding': {'enum': [ENCODING]}, 'data': {'type': 'string'},
        'uncompressed_bytes': {'type': 'integer', 'minimum': 0},
        'uncompressed_sha256': {'type': 'string'}},
        'required': ['encoding', 'data', 'uncompressed_bytes', 'uncompressed_sha256'],
        'additionalProperties': False})
    size = value['uncompressed_bytes']
    require(size <= MAX_DECODED, 'capture_incomplete', 'Decoded JSON exceeds 64 MiB')
    require(re.fullmatch('[0-9a-f]{64}', value['uncompressed_sha256']) is not None,
            'invalid_input', 'Expected a lowercase SHA-256 digest')
    try:
        compressed = base64.b64decode(value['data'], validate=True)
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(compressed, size + 1)
    except (binascii.Error, ValueError, zlib.error):
        raise Fault('invalid_input', 'Malformed base64/zlib envelope') from None
    require(len(decoded) <= size, 'capture_incomplete', 'Decoded JSON exceeds declared length')
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            'invalid_input', 'Truncated or trailing zlib data')
    require(len(decoded) == size and hashlib.sha256(decoded).hexdigest() == value['uncompressed_sha256'],
            'integrity_error', 'Decoded JSON length or SHA-256 mismatch')
    require(not SECRET.search(decoded), 'credential_detected', 'Potential credential; content not retained')
    return _json(decoded), decoded, ENCODING


def inspect_json(workspace, args, paginate, preview):
    validate(args, INSPECT_JSON_SCHEMA)
    raw = read_file(workspace, args['path'])
    document, decoded, encoding = _decode(raw)
    # Screen the decoded document before pointer diagnostics or filtering can
    # expose escaped keys/values. Raw-byte screening alone misses JSON escapes.
    require(not SECRET.search(json.dumps(document).encode()),
            'credential_detected', 'Potential credential; content not retained')
    pointer = args.get('pointer', '')
    value = pointer_value(document, pointer)
    source_total = len(value) if isinstance(value, (dict, list, str)) else None
    indices = None; filter_counts = None
    if 'nonempty_at' in args:
        require(isinstance(value, list), 'invalid_input', 'nonempty_at requires an array selection')
        filter_pointer = args['nonempty_at']
        require(not filter_pointer or filter_pointer.startswith('/'), 'invalid_input', 'Use a JSON pointer for nonempty_at')
        indices = []; filter_counts = {'matched': 0, 'missing': 0, 'empty_or_false': 0}
        for i, item in enumerate(value):
            field = pointer_value(item, filter_pointer, missing_ok=True)
            if field is _MISSING: filter_counts['missing'] += 1
            elif field: indices.append(i)
            else: filter_counts['empty_or_false'] += 1
        filter_counts['matched'] = len(indices)
        value = [value[i] for i in indices]
    elif isinstance(value, list):
        indices = range(len(value))
    page = paginate(value, {'pointer': '', **{k: args[k] for k in ('offset', 'limit') if k in args}})
    if indices is not None:
        start = args.get('offset', 0); page['source_indices'] = list(indices[start:start+args.get('limit', 30)])
    page['value'] = preview(page['value'])
    # JSON escapes must not bypass screening when they become visible text.
    require(not SECRET.search(json.dumps(page['value']).encode()),
            'credential_detected', 'Potential credential; content not retained')
    if filter_counts is not None: page['filter_counts'] = filter_counts
    return {**page, 'pointer': pointer, 'nonempty_at': args.get('nonempty_at'), 'source_total': source_total,
        'source': {'path': args['path'], 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw),
            'encoding': encoding, 'decoded_bytes': len(decoded), 'decoded_sha256': hashlib.sha256(decoded).hexdigest()}}
