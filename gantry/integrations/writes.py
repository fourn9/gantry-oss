"""Prepare, dispatch once, read back and preserve native writes for Core publication."""
import copy
import os
import re
from pathlib import Path
from ..model import Fault, canonical, digest, require
from ..continuity_adapter import SECRET
from ..project_connect import locked, private_dir, save
from .bundle import make_bundle, write_bundle, read_bundle, read_file
from .transport import parse_json, send, send_write
from .write_recipes import validate, observe, write_request, check_response, ATOMIC


def checked(raw):
    require(not SECRET.search(raw), 'credential_detected', 'Potential secret; operation/evidence not saved')
    return raw


def request_view(request):
    return {'method': request.method, 'url': request.url, 'body': parse_json(request.body), 'headers': request.headers}


def prepare(config, change, reason, refs, destination, credential_ref, transport=send):
    pair = validate(config, change)
    require(isinstance(reason, str) and 0 < len(reason) <= 4000, 'invalid_input', 'Reason required')
    checked(canonical([config, change, reason]).encode())
    observation = observe(config, change, credential_ref, transport)
    checked(observation['raw'])
    request = write_request(config, change, observation['baseline'])
    plan = {'version': 1, 'target': copy.deepcopy(config), 'change': copy.deepcopy(change),
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
    require(set(plan) == {'version','target','change','reason','requirement_refs','baseline','desired','concurrency','request'}
            and plan['version'] == 1 and plan['requirement_refs'] == bundle['manifest']['requirement_refs'],
            'integrity_error', 'Invalid write plan')
    require(plan['request'] == request_view(write_request(plan['target'],plan['change'],plan['baseline'])),
            'integrity_error', 'Write recipe differs from plan')
    plan_hash = digest(plan)
    require(bundle['manifest']['source'] == {'native_write_plan': plan_hash}, 'integrity_error', 'Plan digest mismatch')
    return plan, plan_hash, bundle


def journal_path(directory, plan_hash):
    path = Path(directory).absolute()
    require(not path.is_symlink(), 'scope_denied', 'Journal cannot be a symlink')
    return private_dir(path.resolve())/(plan_hash+'.json')


def persist(path, value):
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
    receipt = journal_path(journal, plan_hash)
    with locked(str(receipt)+'.lock'):
        if receipt.exists(): return read_receipt(receipt)
        current = observe(plan['target'],plan['change'],credential_ref,transport or send)
        require(current['baseline'] == plan['baseline'], 'stale_basis', 'External baseline changed; prepare a new plan')
        outcome = {'plan_hash': plan_hash, 'status': 'dispatching', 'concurrency': plan['concurrency']}
        persist(receipt, outcome)
        try:
            response = (transport(write_request(plan['target'],plan['change'],plan['baseline']),credential_ref)
                        if transport else send_write(plan['target'],plan['change'],plan['baseline'],credential_ref))
            checked(response.raw)
            check_response(plan['target'],response)
            outcome['response'] = response.raw.decode('utf-8') if response.raw else ''
            outcome['status'] = 'applied_unverified'
            persist(receipt,outcome)
        except Fault as exc:
            # Even an error after dispatch may hide an applied write. Never resend automatically.
            refused = {'remote_http_400','remote_http_401','remote_http_403','remote_http_404',
                       'remote_http_409','remote_http_412','remote_http_422','rate_limited','remote_error'}
            outcome.update(status='refused' if exc.code in refused else 'unknown', error=exc.code)
            persist(receipt,outcome); return outcome
        return _readback(plan,receipt,outcome,credential_ref,transport or send,False)


def _readback(plan,receipt,outcome,credential_ref,transport,recovery):
    try:
        current = observe(plan['target'],plan['change'],credential_ref,transport)
        checked(current['raw'])
        outcome['after'] = current['raw'].decode('utf-8')
        outcome['observed_revision'] = current['baseline']['revision']
        matches = current['baseline']['value'] == plan['desired']
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
