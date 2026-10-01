"""Outbound subscription worker for Core-assigned roles and customer edits."""
import json
import threading
import subprocess
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from .client import Client
from .model import Fault, require, uid, digest, canonical
from .contracts import validate
from .runner import persist, restore_files, validate_recipe, process_env, stop_process
from .development import in_scope
from .mentor_jobs import JOB_SCHEMAS
from .monthly_codex import infer_monthly
from .mentor_input import compact_review, collect_files
from .continuity_adapter import capture_workspace


def tree_fingerprint(root):
    files={}
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink():raise Fault('scope_denied','Symlinks not allowed in automated edit workspace')
        if p.is_file():files[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return digest(files)


def process_job(client,job_id,journal,infer_fn=infer_monthly,cad_python=None,verification=None):
    root=Path(journal)/digest(job_id);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    import fcntl
    with open(root/'lock','a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'busy','job_id':job_id}
        path=root/'job.json'
        j=json.loads(path.read_text()) if path.exists() else {'phase':'new','key':uid('mentor-job')}
        require(not j.get('pending_recovery'), 'recovery_pending', 'Finish the durable recovery request before working')
        if j['phase']=='done':return j['result']
        if j['phase']=='new':
            persist(path,j)
            job=client.call('claim_mentor_job',{'job_id':job_id,'lease_seconds':900, **({'verification_hash':digest(verification)} if verification else {})},j['key']+':claim')
            j.update(phase='claimed',job=job);persist(path,j)
        job=j['job']; context=job['context']
        if j['phase'] in {'claimed','inference','output_saved','edits_applied','verified'}:
            client.call('check_mentor_job',{'job_id':job_id,'fence':job['fence']})
        if j['phase']=='claimed':
            workspace=root/'workspace'
            input_development=context.get('returned_development',context['development'])
            if not workspace.exists():restore_files(client,input_development['state']['snapshot'],workspace,cache_dir=root.parent/'.cache')
            review=compact_review(context)
            files,coverage=collect_files(workspace,max_total=max(0,min(200000,400000-len(canonical(review).encode()))),priority_text=context.get('question',''))
            ctx={'role':job['role'],'task':job['kind'],'review':review,'files':files,'input_coverage':coverage, 'files_state_id':input_development['state']['id'],
                 'instruction':{'specialist':'Review your discipline, cite supplied state IDs; report unresolved conditions.',
                     'coordinator':'Integrate specialist reports and inspect supplied requirements, source files, prior failures and engineering declarations. '
                         'Return engineering_plan with newly inferred component roles/assemblies and missing verification checks; use empty arrays with explicit limitations if evidence is insufficient. '
                         'Do not duplicate or overwrite existing component/check IDs; reference existing components when possible. Cite evidence IDs and exact existing source paths. '
                         'For each new check state scope, method, acceptance, rationale, required and a finding_id linking to an actionable finding. '
                         'Separate placement, motion, service/removal and connection checks when relevant to the submitted stage. Never infer a pass from a file existing. '
                         'Proposed checks are unverified; a test method is a suggestion, not permission to execute arbitrary commands. '
                         'Core accepts ok ONLY if findings, unverified and ALL specialist unresolved arrays are empty and required checks are satisfied. '
                         'Otherwise use conditional, changes_requested or insufficient_evidence. Include concrete source-level edits for changes_requested.',
                     'developer':'Implement the review findings and engineering_proposal by returning full UTF-8 contents of changed source files only. '
                         'Implement suggested evaluators where feasible within delegated scope; do not invent results or weaken acceptance criteria. '
                         'Use the configured verification recipe only; list checks that need another tool or execution permission in unverified. '
                         'Core carries inferred roles/checks into the checkpoint as unverified; successful execution alone never marks all checks passed.',
                     'reflection':'Compare prior prediction to returned candidate and available evidence. A changed file alone is inconclusive about engineering success. State applicability and limitations.'}[job['kind']]}
            if cad_python:
                from .review_context import inspect_cad
                paths=[p.relative_to(workspace).as_posix() for p in workspace.rglob('*') if p.suffix.lower() in {'.step','.stp','.stl'}][:20]
                if paths:
                    baseline=root/'baseline'
                    if not baseline.exists():restore_files(client,context['baseline']['snapshot'],baseline,cache_dir=root.parent/'.cache')
                    ctx['cad_inspection']=inspect_cad(workspace,paths,baseline_root=baseline,python_executable=cad_python)
            j.update(phase='inference',input=ctx);persist(path,j)
        if (j['phase']=='inference' and infer_fn is infer_monthly
                and not (root/j.get('model_directory','model')/'inference.json').exists()
                and j['input'].get('review',{}).get('inference_view',{}).get('version',0) < 2):
            # Preserve the old view for auditing. Do not replay an uncertain provider call.
            persist(root/'legacy-inference-input.json',j['input'])
            review=compact_review(context)
            files,coverage=collect_files(root/'workspace',max_total=max(0,min(200000,400000-len(canonical(review).encode()))),priority_text=context.get('question',''))
            j['input'].update(review=review,files=files,input_coverage=coverage)
            persist(path,j)
        if j['phase']=='inference':
            schema=json.loads(json.dumps(JOB_SCHEMAS[job['kind']]))
            if job['kind']=='coordinator':
                schema['required'].append('engineering_plan')
                schema['properties']['engineering_plan']['type']='object'
            refs=[context['state_id'],context['base_state']] + [e['id'] for e in context['development']['evaluations'] if e['state_id']==context['state_id']]
            refs += [x['reference_id'] for x in context.get('related',{}).get('items',[])]
            def restrict(node):
                for name, prop in node.get('properties',{}).items():
                    if name=='evidence':prop['items']={'type':'string','enum':sorted(set(refs))}
                    restrict(prop)
                if 'items' in node:restrict(node['items'])
            restrict(schema)
            if job['kind']=='coordinator' and any(x['unresolved'] for x in context['specialists'].values()):
                schema['properties']['verdict']['enum']=['conditional','changes_requested','insufficient_evidence']
            receipt=infer_fn(j['input'],schema,root/j.get('model_directory','model'))
            validate(receipt['output'],schema)
            if j['input'].get('cad_inspection'):receipt['provider']['cad_inspection']=j['input']['cad_inspection']
            j.update(phase='output_saved',receipt=receipt);persist(path,j)
        if j['phase']=='output_saved':
            output=j['receipt']['output']
            if job['kind']=='developer':
                workspace=root/'workspace';seen=set()
                for edit in output['edits']:
                    name=edit['path'];p=Path(name)
                    require(not p.is_absolute() and '..' not in p.parts and name not in seen,'scope_denied','Invalid or duplicate edit path')
                    require(in_scope(name,context['change']['write_scope']) and in_scope(name,context['write_scope']), 'scope_denied','Edit outside delegation')
                    target=workspace/p;require(not target.is_symlink() and workspace.resolve() in target.resolve().parents,'scope_denied','Unsafe edit path')
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(edit['content']);seen.add(name)
                j.update(phase='edits_applied', edit_fingerprint=tree_fingerprint(workspace));persist(path,j)
            else:
                j.update(phase='returning',output=output);persist(path,j)
        if j['phase']=='edits_applied':
            workspace=root/'workspace'
            require(job.get('verification_hash') == (digest(verification) if verification else None),
                    'recipe_not_allowed','Verification configuration differs from reserved job')
            if verification:
                validate_recipe(verification); report_path=root/'verification.json'
                if report_path.exists():
                    report=json.loads(report_path.read_text())
                    require(report.get('status')=='completed','outcome_unknown','Verification outcome uncertain; inspect before retry')
                    require(report['recipe_hash']==digest(verification) and report['output_fingerprint']==tree_fingerprint(workspace),
                            'stale_basis','Verified bytes or recipe changed')
                else:
                    require(tree_fingerprint(workspace)==j['edit_fingerprint'],'stale_basis','Edited files changed before verification')
                    client.call('check_mentor_job',{'job_id':job_id,'fence':job['fence']})
                    persist(report_path,{'status':'started','recipe_hash':digest(verification)})
                    with open(root/'verification.stdout','w') as out,open(root/'verification.stderr','w') as err:
                        proc=subprocess.Popen(verification['argv'],cwd=workspace,env=process_env(verification),stdout=out,stderr=err,start_new_session=True)
                        persist(report_path,{'status':'started','recipe_hash':digest(verification),'pid':proc.pid})
                        try:proc.wait(timeout=verification.get('timeout_seconds',30))
                        except subprocess.TimeoutExpired:stop_process(proc);raise Fault('verification_timeout','Verification stopped at timeout')
                    report={'status':'completed','recipe_hash':digest(verification),'exit_code':proc.returncode,
                            'input_fingerprint':j['edit_fingerprint'],'output_fingerprint':tree_fingerprint(workspace),
                            'stdout':(root/'verification.stdout').read_text()[-16000:],'stderr':(root/'verification.stderr').read_text()[-16000:]}
                    persist(report_path,report)
                j['receipt']['provider']['verification']=report
                if report.get('outcome') == 'interrupted_unknown':
                    j['receipt']['output']['unverified'].append('Verification interrupted; partial output collected without a pass')
                fingerprint=report['output_fingerprint']
            else:fingerprint=j['edit_fingerprint']
            j.update(phase='verified',output_fingerprint=fingerprint);persist(path,j)
        if j['phase']=='verified':
            workspace=root/'workspace'
            require(tree_fingerprint(workspace)==j['output_fingerprint'],'stale_basis','Files changed after verification')
            artifact,missing=capture_workspace(client,workspace,j['key']+':capture')
            require(tree_fingerprint(workspace)==j['output_fingerprint'],'stale_basis','Files changed during capture')
            output={k:j['receipt']['output'][k] for k in ('summary','hypothesis','rationale','unverified')}
            output.update(snapshot=artifact['revision_id'],capture={'scope':'restored source files and returned edits; no hidden agent reasoning','missing':missing})
            j.update(phase='returning',output=output);persist(path,j)
        result=client.call('finish_mentor_job',{'job_id':job_id,'fence':job['fence'],'output':j['output'],
            'provider':j['receipt']['provider']},j['key']+':finish')
        j.update(phase='done',result=result);persist(path,j);return result


def tick_mentor(config,journal,infer_fn=infer_monthly):
    # Credential files are local operator configuration, never placed in model context.
    clients={pid:Client(config['url'],Path(path).read_text().strip()) for pid,path in config['principals'].items()}
    if not clients:return []
    first=next(iter(clients.values()));tasks=[]
    for sid in config['sessions']:
        status=first.call('review_automation_status',{'session_id':sid})
        for job in status['jobs']:
            if job['status'] in {'pending','running','interrupted'} and job['principal_id'] in clients:
                tasks.append((clients[job['principal_id']],job['id']))
    def run(task):
        try:return process_job(*task,journal,infer_fn,config.get('cad_python'),config.get('verification'))
        except (Fault,OSError,ValueError) as exc:
            reason=exc.code if isinstance(exc,Fault) else type(exc).__name__
            if isinstance(exc,Fault) and reason in {'outcome_unknown','provider_timeout','provider_failed','scope_denied','invalid_input','verification_timeout','stale_basis'}:
                path=Path(journal)/digest(task[1])/'job.json'
                if path.exists():
                    saved=json.loads(path.read_text());job=saved.get('job')
                    if job:
                        try:task[0].call('fail_mentor_job',{'job_id':job['id'],'fence':job['fence'],'reason':reason},saved['key']+':fail')
                        except Fault:pass
            return {'job_id':task[1],'status':'held','reason':reason}
    with ThreadPoolExecutor(max_workers=min(4,max(1,config.get('parallel',2)))) as pool:return list(pool.map(run,tasks))


def run_mentor(config,journal,iterations=1,interval=10):
    require(iterations>=0 and 1<=interval<=60,'invalid_input','Invalid polling settings')
    stop=threading.Event();count=0
    try:
        while iterations==0 or count<iterations:
            print(json.dumps(tick_mentor(config,journal)),flush=True);count+=1
            if iterations==0 or count<iterations:stop.wait(interval)
    except KeyboardInterrupt:pass
