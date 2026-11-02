"""Explicit native update recipes; no caller-controlled methods, URLs or auth headers."""
import base64
import copy
import re
from urllib.parse import quote, urlencode
from ..model import Fault, canonical, require
from .bundle import safe_file
from .transport import ReadRequest, parse_json, send

OPERATIONS = {'github': {'file.update'}}
TARGETS = {('github', 'file.update'): {'repository', 'branch', 'path'}}
ATOMIC = {('github', 'file.update')}


def validate(config, change):
    require(isinstance(config, dict) and isinstance(change, dict), 'invalid_input', 'Target and change objects required')
    pair = (config.get('provider'), config.get('operation'))
    require(pair in TARGETS, 'unsupported', 'Native update operation is not supported')
    require(set(config) == TARGETS[pair] | {'provider', 'operation'}, 'invalid_input', 'Exact native target fields required')
    for key, value in config.items():
        require(isinstance(value, str) and 0 < len(value) <= 1000 and not any(ord(c) < 32 for c in value),
                'invalid_input', 'Bounded target strings required')
        require('\\' not in value and all(p not in {'', '.', '..'} for p in value.split('/')),
                'invalid_input', 'Invalid target identifier')
    require(len(canonical(change).encode()) <= 1024*1024, 'acquisition_limit', 'Update exceeds 1 MiB')
    if pair == ('github', 'file.update'):
        from ..github_connector import validate_repository
        validate_repository(config['repository']); safe_file(config['path'])
        require(set(change) == {'content', 'message'} and isinstance(change['content'], str)
                and isinstance(change['message'], str) and 0 < len(change['message']) <= 1000,
                'invalid_input', 'UTF-8 file content and commit message required')
    return pair


def read_request(config):
    # Called only after validate(config, change).
    base = 'https://api.github.com/repos/' + config['repository'] + '/contents/' + quote(config['path'], safe='/')
    return ReadRequest(base + '?' + urlencode({'ref': config['branch']}), headers={
        'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})


def observe(config, change, credential_ref, transport=send):
    validate(config, change)
    response = transport(read_request(config), credential_ref)
    require(isinstance(response.raw, bytes) and len(response.raw) <= 8*1024*1024,
            'acquisition_limit', 'Bounded response required')
    data = parse_json(response.raw)
    require(isinstance(data, dict) and not data.get('errors') and not data.get('error'),
            'invalid_response', 'Expected successful object response')
    require(data.get('type') == 'file' and data.get('path') == config['path']
            and data.get('encoding') == 'base64' and re.fullmatch('[a-f0-9]{40,64}', data.get('sha', '')),
            'invalid_response', 'Requested regular repository file required')
    try: content = base64.b64decode(''.join(data['content'].split()), validate=True).decode('utf-8')
    except (ValueError, KeyError, UnicodeError): raise Fault('invalid_response', 'UTF-8 repository content required') from None
    return {'raw': response.raw, 'baseline': {'revision': data['sha'], 'value': {'content': content}},
            'desired': {'content': change['content']}}


def write_request(config, change, baseline):
    validate(config, change)
    req = read_request(config)
    body = {'message': change['message'], 'content': base64.b64encode(change['content'].encode()).decode(),
            'branch': config['branch'], 'sha': baseline['revision']}
    return ReadRequest(req.url.split('?')[0], 'PUT', canonical(body).encode(), req.headers, req.auth)


def check_response(config, response):
    if response.raw:
        data = parse_json(response.raw)
        require(isinstance(data, dict) and not data.get('error') and not data.get('errors'),
                'remote_error', 'Native update returned an error')
