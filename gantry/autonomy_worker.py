"""Restartable, outbound autonomous analyst. Multiple worker processes are safe.

Server leases fence independent journals/machines. A local journal replays a
saved response rather than purchasing another inference after a lost ACK.
An uncertain launch is recorded as such, never blindly repeated.
"""
import json
import os
import signal
import threading
from pathlib import Path
from .model import Fault, require, uid
from .runner import persist
from .inference import infer
from .contracts import validate, CONTRACTS


def analyst_once(client,config,journal,worker_id,infer_fn=None):
    require(config.get('project_ids'),'invalid_input','Explicit project_ids required')
    root=Path(journal);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    import fcntl
    with open(root/'lock','a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'held','reason':'local_worker_active'}
        path=root/'active.json';j=json.loads(path.read_text()) if path.exists() else None
        if j:
            require(j['worker_id']==worker_id,'conflict','Journal belongs to another worker')
            run=client.call('get_analysis',{'analysis_id':j['run']['id']})
            if run['status']!='running':
                persist(root/(run['id']+'.json'),dict(j,server_status=run['status']))
                path.unlink();return {'status':'recovered','analysis_id':run['id'],'server_status':run['status']}
        else:
            # Mentor has priority after outcomes/dependency changes; one claim per tick.
            waiting=[];run=None
            for kind in ('mentor','triage'):
                for pid in config['project_ids']:
                    result=client.call('claim_analysis',{'project_id':pid,'kind':kind,'worker_id':worker_id})
                    if result['status']=='claimed':run=result['run'];break
                    waiting.append(dict(project_id=pid,kind=kind,**result))
                if run:break
            if not run:return {'status':'idle','queues':waiting}
            j={'worker_id':worker_id,'run':run,'phase':'claimed'};persist(path,j)
        heartbeat={'worker_id':worker_id,'kind':'analyst','project_ids':config['project_ids'],
            'session_ids':[run['session_id']] if run['session_id'] else [],'status':'working',
            'summary':run['kind']+' · '+run['provider']['kind']+' / '+run['provider']['model']}
        client.call('worker_heartbeat',heartbeat)
        if j['phase']=='claimed':
            j['phase']='request_started';persist(path,j)
            try:
                receipt=(infer_fn or infer)(run,config.get('provider',{}))
                validate({'analysis_id':run['id'],'fence':run['fence'],**receipt}, CONTRACTS['complete_analysis']['schema'])
                j.update(phase='response_saved',receipt=receipt)
            except (Fault,OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
                j.update(phase='failed',error=exc.code if isinstance(exc,Fault) else 'provider_invalid_response')
            persist(path,j)
        elif j['phase']=='request_started':
            j.update(phase='failed',error='request_outcome_unknown');persist(path,j)
        args={'analysis_id':run['id'],'fence':run['fence']}
        if j['phase']=='response_saved':
            result=client.call('complete_analysis',{**args,**j['receipt']},run['id']+':complete')
        else:
            result=client.call('fail_analysis',{**args,'code':j['error']},run['id']+':fail')
        j['result']=result;persist(root/(run['id']+'.json'),j);path.unlink()
        client.call('worker_heartbeat',{**heartbeat,'status':'idle','summary':'Waiting for new evidence'})
        return result


def run_analyst(client,config,journal,worker_id=None,iterations=0,interval=15):
    require(iterations>=0 and 1<=interval<=60,'invalid_input','Iterations >= 0 and interval 1–60 seconds required')
    worker_id=worker_id or 'analyst-'+uid('worker')[-12:]
    stop=threading.Event()
    def shutdown(*unused):stop.set()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,shutdown)
    index=0
    while not stop.is_set() and (iterations==0 or index<iterations):
        try:
            result=analyst_once(client,config,journal,worker_id)
            reasons=sorted({q['reason'] for q in result.get('queues',[]) if q.get('reason')})
            summary=('Held: '+', '.join(reasons)) if reasons else 'Watching Incoming, failures and dependency changes'
            client.call('worker_heartbeat',{'worker_id':worker_id,'kind':'analyst','project_ids':config['project_ids'],
                'session_ids':[],'status':'idle','summary':summary})
            print(json.dumps({'iteration':index+1,'result':result}),flush=True)
        except (Fault,OSError,ValueError) as exc:
            print(json.dumps({'iteration':index+1,'error':exc.code if isinstance(exc,Fault) else 'worker_failed'}),flush=True)
        index+=1
        if iterations==0 or index<iterations:stop.wait(interval)
    client.call('worker_heartbeat',{'worker_id':worker_id,'kind':'analyst','project_ids':config['project_ids'],
        'session_ids':[],'status':'stopped','summary':'Analyst stopped; pending work remains in the ledger'})
