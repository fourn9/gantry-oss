"""Prepare, dispatch once, read back and preserve native writes for Core publication."""
import copy
import os
import re
import secrets
from pathlib import Path
from datetime import datetime, timezone
from ..model import Fault, canonical, digest, require
from ..continuity_adapter import SECRET
from ..project_connect import locked, private_dir, save
from .bundle import make_bundle, write_bundle, read_bundle, read_file
from .transport import parse_json, send, send_write, Response
from .write_recipes import validate, observe, write_request, check_response, ATOMIC


def checked(raw, credential_ref=None):
    require(not SECRET.search(raw), 'credential_detected', 'Potential secret; operation/evidence not saved')
    token = os.environ.get(credential_ref, '') if isinstance(credential_ref,str) else ''
    require(not token or token.encode() not in raw, 'credential_detected', 'Configured credential in decoded data')
    return raw


def request_view(request):
    return {'method': request.method, 'url': request.url, 'body': parse_json(request.body), 'headers': request.headers}


def prepare(config, change, reason, refs, destination, credential_ref, transport=send):
    pair = validate(config, change)
    require(isinstance(reason, str) and 0 < len(reason) <= 4000, 'invalid_input', 'Reason required')
    checked(canonical([config, change, reason]).encode(),credential_ref)
    observation = observe(config, change, credential_ref, transport)
    checked(observation['raw'],credential_ref)
    checked(canonical(observation['baseline']).encode(),credential_ref)
    request = write_request(config, change, observation['baseline'])
    plan = {'version': 1, 'intent_id': secrets.token_hex(16), 'target': copy.deepcopy(config), 'change': copy.deepcopy(change),
            'reason': reason, 'requirement_refs': copy.deepcopy(refs), 'baseline': observation['baseline'],
            'desired': observation['desired'], 'concurrency': 'provider_condition' if pair in ATOMIC else 'preflight_only',
            'request': request_view(request)}
    plan_hash = digest(plan)
    bundle = make_bundle(config['provider'], 'write-'+plan_hash[:24],
                         {'plan.json': canonical(plan).encode(), 'before.json': observation['raw']}, refs,
                         source={'native_write_plan': plan_hash}, missing=['not applied'])
    write_bundle(destination, bundle)
    return {'plan_hash': plan_hash, 'plan': plan, 'remote_write': False}


def load_plan(path):
    bundle = read_bundle(path)
    plan = parse_json(bundle['files']['plan.json'])
    validate(plan['target'], plan['change'])
    require(set(plan) == {'version','intent_id','target','change','reason','requirement_refs','baseline','desired','concurrency','request'}
            and plan['version'] == 1 and isinstance(plan['intent_id'],str) and re.fullmatch('[a-f0-9]{32}',plan['intent_id'])
            and plan['requirement_refs'] == bundle['manifest']['requirement_refs'],
            'integrity_error', 'Invalid write plan')
    require(plan['request'] == request_view(write_request(plan['target'],plan['change'],plan['baseline'])),
            'integrity_error', 'Write recipe differs from plan')
    before = observe(plan['target'], plan['change'], None,
                     lambda *args: Response(bundle['files']['before.json'], {}))
    pair = (plan['target']['provider'], plan['target']['operation'])
    require(canonical(before['baseline']) == canonical(plan['baseline'])
            and canonical(before['desired']) == canonical(plan['desired'])
            and plan['concurrency'] == ('provider_condition' if pair in ATOMIC else 'preflight_only'),
            'integrity_error', 'Plan does not match its original observation')
    plan_hash = digest(plan)
    require(bundle['manifest']['source'] == {'native_write_plan': plan_hash}, 'integrity_error', 'Plan digest mismatch')
    return plan, plan_hash, bundle


def journal_path(directory, plan_hash):
    path = Path(directory).absolute()
    require(not path.is_symlink(), 'scope_denied', 'Journal cannot be a symlink')
    return private_dir(path.resolve())/(plan_hash+'.json')


def persist(path, value):
    value.setdefault('history', []).append({'status':value['status'],
        'recorded_at':datetime.now(timezone.utc).isoformat(),
        **({'error':value['error']} if 'error' in value else {})})
    checked(canonical(value).encode())
    save(path, value)
    # Persist rename before the external effect; file fsync alone is insufficient.
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def read_receipt(path):
    return parse_json(read_file(path.parent, path.name))


def apply(path, expected_hash, journal, credential_ref, allow_nonatomic=False, transport=None):
    plan, plan_hash, _ = load_plan(path)
    require(expected_hash == plan_hash, 'integrity_error', 'Explicit matching plan hash required')
    pair = (plan['target']['provider'], plan['target']['operation'])
    require(pair in ATOMIC or allow_nonatomic is True, 'nonatomic_write',
            'Provider has no atomic version condition for this operation; explicitly allow preflight-only writes')
    require(isinstance(credential_ref,str) and re.fullmatch('GANTRY_CONNECTOR_[A-Z0-9_]+',credential_ref),
            'credential_missing','Explicit operator credential reference required')
    checked(canonical(plan).encode(),credential_ref)
    receipt = journal_path(journal, plan_hash)
    with locked(str(receipt)+'.lock'):
        if receipt.exists(): return read_receipt(receipt)
        current = observe(plan['target'],plan['change'],credential_ref,transport or send)
        checked(canonical(current['baseline']).encode(),credential_ref)
        require(canonical(current['baseline']) == canonical(plan['baseline']), 'stale_basis', 'External baseline changed; prepare a new plan')
        outcome = {'plan_hash': plan_hash, 'status': 'dispatching', 'concurrency': plan['concurrency']}
        if canonical(current['baseline']['value']) == canonical(plan['desired']):
            outcome.update(status='unchanged', after=checked(current['raw']).decode('utf-8'),
                           observed_revision=current['baseline']['revision'])
            persist(receipt,outcome); return outcome
        persist(receipt, outcome)
        try:
            response = (transport(write_request(plan['target'],plan['change'],plan['baseline']),credential_ref)
                        if transport else send_write(plan['target'],plan['change'],plan['baseline'],credential_ref))
            require(len(response.raw)<=2*1024*1024,'acquisition_limit','Write response exceeds 2 MiB')
            checked(response.raw)
            check_response(plan['target'],response)
            outcome['response'] = response.raw.decode('utf-8') if response.raw else ''
            outcome['status'] = 'applied_unverified'
            persist(receipt,outcome)
        except Fault as exc:
            # Even an error after dispatch may hide an applied write. Never resend automatically.
            refused = {'remote_http_400','remote_http_401','remote_http_403','remote_http_404',
                       'remote_http_409','remote_http_412','remote_http_422','rate_limited'}
            outcome.update(status='refused' if exc.code in refused else 'unknown', error=exc.code)
            persist(receipt,outcome); return outcome
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError):
            outcome.update(status='unknown',error='invalid_response_or_local_io')
            persist(receipt,outcome); return outcome
        return _readback(plan,receipt,outcome,credential_ref,transport or send,False)


def _readback(plan,receipt,outcome,credential_ref,transport,recovery):
    try:
        current = observe(plan['target'],plan['change'],credential_ref,transport)
        checked(current['raw'],credential_ref)
        checked(canonical(current['baseline']).encode(),credential_ref)
        outcome['after'] = current['raw'].decode('utf-8')
        outcome['observed_revision'] = current['baseline']['revision']
        matches = canonical(current['baseline']['value']) == canonical(plan['desired'])
        outcome['status'] = ('observed_desired' if recovery else 'verified') if matches else 'readback_mismatch'
        outcome['write_verification'] = 'selected_fields_only_not_engineering_acceptance'
    except Fault as exc:
        outcome.update(status='unknown' if recovery else 'applied_unverified', error=exc.code)
    persist(receipt,outcome); return outcome


def reconcile(path,journal,credential_ref,transport=send):
    plan,plan_hash,_ = load_plan(path); receipt=journal_path(journal,plan_hash)
    with locked(str(receipt)+'.lock'):
        require(receipt.exists(),'not_found','No dispatch receipt to reconcile')
        outcome=read_receipt(receipt)
        return _readback(plan,receipt,outcome,credential_ref,transport,True)


def evidence(path,journal):
    plan,plan_hash,bundle=load_plan(path);receipt=journal_path(journal,plan_hash)
    with locked(str(receipt)+'.lock'):
        require(receipt.exists(),'not_found','No dispatch receipt')
        outcome=read_receipt(receipt)
    files=dict(bundle['files']);files['receipt.json']=canonical(outcome).encode()
    if 'after' in outcome: files['after.json']=outcome['after'].encode()
    if outcome.get('response'): files['write-response.json']=outcome['response'].encode()
    return make_bundle(plan['target']['provider'],bundle['manifest']['source_id'],files,plan['requirement_refs'],
        source={'native_write_plan':plan_hash,'target':plan['target'],'outcome':outcome['status']},
        missing=['engineering validation not performed','native dependencies outside selected object not captured'],
        source_revision=outcome.get('observed_revision'))
