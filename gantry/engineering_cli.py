"""One local engineering path: checkout, edit, publish, evaluate, collect, review."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from .model import Fault, canonical, digest, require
from . import engineering_workflow as workflow
from .physical_execution import read
from .workflow_journal import measure, timing_report, start_span, transition


def doctor():
    from .native.catalog import catalog
    try: cad=importlib.metadata.version('cadquery')
    except importlib.metadata.PackageNotFoundError: cad=None
    try:
        from .cad_kernel import BACKEND
        backend = {'ready_for_smoke_test':True,'backend':BACKEND,'runtime_verified':False}
    except ImportError as error:
        backend = {'ready_for_smoke_test':False,'reason':str(error),'runtime_verified':False}
    return {'cad_backend':backend,'python':platform.python_version(),'platform':platform.system(),
        'cadquery':{'installed_version':cad,'ready_for_smoke_test':False,'external_environment_only':True,
                    'runtime_verified':False,'next':'Run examples/engineering_roundtrip.py with this interpreter'},
        'native_products':catalog(),
        'core_connection':'not checked; use status on an authenticated checkout',
        'limits':{'input_files':100,'input_total_MiB':256,'report_MiB':1},
        'security':['Local evaluator runs with caller OS permissions; recipe hash is authorization, not a sandbox',
            'Tokens remain outside snapshots; no telemetry or model service is contacted by this command'],
        'qualification':'Installation detected is not native read/write qualification'}


def execute(a):
    if a.command=='doctor': return doctor()
    if a.command=='timing':
        if a.action=='report':
            result=timing_report(a.journal)
            if a.output:
                with Path(a.output).open('x') as f: f.write(canonical(result))
            return result
        if a.action=='start': return {'span_id':start_span(a.journal,a.phase,a.state_id,a.operation,a.parent_id)}
        return {'span_id':transition(a.journal,a.span_id,a.action,a.outcome)}
    if a.command=='recipe-hash': return {'approved_hash':digest(json.loads(Path(a.recipe).read_text()))}
    if a.command=='collect':
        from .physical_execution import collect
        return collect(a.job,a.root,a.replace_report_sha256)
    if a.command=='reconcile':
        from .physical_execution import reconcile
        return reconcile(a.job,a.process_stopped)
    if a.command=='edit':
        from .cad_io import edit
        request=json.loads(Path(a.request).read_text())
        with measure(workflow.local(a.root),'editing','local',digest(request)):
            return edit(a.root,request,a.output)
    require(a.url and a.token_file,'invalid_input','--url and --token-file required for Core operations')
    from .client import Client
    client=Client(a.url,Path(a.token_file).read_text().strip())
    if a.command=='checkout':
        return workflow.checkout(client,a.state_id,a.destination,a.title,a.purpose,a.scope,a.assignee,a.key)
    if a.command=='status': return workflow.status(client,a.root)
    if a.command=='bind': return workflow.bind_mapping(client,a.root,a.mapping,a.reason,a.key)
    if a.command=='publish': return workflow.publish(client,a.root,a.plan,a.key)
    if a.command=='capture': return workflow.capture(client,a.root,a.bundle,a.key)
    if a.command=='checkpoint': return workflow.checkpoint(client,a.root,a.summary,a.reason,a.key)
    info=workflow.link(client,a.root)
    if a.command=='evaluate':
        view=client.call('get_development_state',{'state_id':info['state_id']})
        require(not any(r.get('status')=='needs_review' for r in view.get('requirement_coverage',{}).get('items',[])),
                'stale_basis','Requirements changed; reassess before running')
        listing=client.call('list_development_states',{'session_id':view['state']['session_id']})
        change=next((c for c in listing['changes'] if c['id']==info['change_id']),None)
        require(change and change['head']==info['state_id'] and change['version']==info['version'],
                'stale_basis','Change advanced; inspect status before running')
        plan=json.loads(read(a.root,a.plan,1024**2))
        check=next((c for c in plan['checks'] if c['id']==a.check_id),None)
        require(check,'not_found','Check missing from plan')
        for p in [a.plan,*check['inputs']]:
            require(view['manifest'].get(p,{}).get('hash')==hashlib.sha256(read(a.root,p)).hexdigest(),
                    'stale_basis','Publish candidate inputs before evaluating')
        from .physical_execution import run
        return run(a.root,a.plan,a.check_id,json.loads(Path(a.recipe).read_text()),a.approved_hash,a.job,info['state_id'])
    if a.command=='review':
        from .workflow_journal import freeze
        journal=workflow.local(a.root)
        request={'change_id':info['change_id'],'version':info['version'],'question':a.question,
            'stage':a.stage,'acceptance':a.acceptance,'required_roles':a.required_role}
        args=freeze(journal,'review:'+a.key,[info['endpoint'],a.question,a.stage,a.acceptance,a.required_role],lambda:request)
        with measure(journal,'review',info['state_id'],a.key):
            return client.call('submit_change_review',args,a.key+':review')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url'); p.add_argument('--token-file')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    checkout=sub.add_parser('checkout')
    for name in ('state-id','destination','title','purpose','assignee','key'): checkout.add_argument('--'+name,required=True)
    checkout.add_argument('--scope',action='append',required=True)
    for command in ('status','bind','publish','edit','evaluate','collect','review','checkpoint','capture'):
        cmd=sub.add_parser(command); cmd.add_argument('--root',required=True)
        if command in {'bind','publish','review','checkpoint','capture'}: cmd.add_argument('--key',required=True)
        if command=='capture': cmd.add_argument('--bundle',required=True)
        if command=='checkpoint':
            cmd.add_argument('--summary',required=True); cmd.add_argument('--reason',required=True)
        if command=='bind':
            cmd.add_argument('--mapping',required=True); cmd.add_argument('--reason',required=True)
        if command in {'publish','evaluate'}: cmd.add_argument('--plan',default='physical-plan.json')
        if command=='edit':
            cmd.add_argument('--request',required=True); cmd.add_argument('--output',required=True)
        if command in {'evaluate','collect'}: cmd.add_argument('--job',required=True)
        if command=='evaluate':
            for name in ('check-id','recipe','approved-hash'): cmd.add_argument('--'+name,required=True)
        if command=='collect': cmd.add_argument('--replace-report-sha256')
        if command=='review':
            cmd.add_argument('--question',required=True)
            cmd.add_argument('--stage',choices=['concept','preliminary','detailed','integration'],required=True)
            cmd.add_argument('--acceptance',action='append',required=True)
            cmd.add_argument('--required-role',action='append',required=True)
    recipe=sub.add_parser('recipe-hash'); recipe.add_argument('--recipe',required=True)
    recovery=sub.add_parser('reconcile'); recovery.add_argument('--job',required=True)
    recovery.add_argument('--process-stopped',action='store_true')
    timing=sub.add_parser('timing'); timing.add_argument('--journal',required=True)
    timing.add_argument('action',choices=['start','pause','resume','finish','report'])
    for name in ('span-id','phase','state-id','operation','parent-id','output'): timing.add_argument('--'+name)
    timing.add_argument('--outcome',default='completed')
    try: print(json.dumps(execute(p.parse_args()),ensure_ascii=False,indent=2))
    except (Fault,ValueError,OSError,KeyError,TypeError) as exc:
        print(canonical({'error':exc.as_dict() if isinstance(exc,Fault) else
                         {'code':'local_error','message':type(exc).__name__}}),file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__': main()
