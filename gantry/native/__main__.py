"""Customer-local native API CLI. Use --help; no vendor application is installed or launched."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from ..model import Fault,canonical,require,digest
from ..integrations.bundle import make_bundle,write_bundle,read_file
from ..integrations.transport import parse_json
from . import workflow
from .catalog import catalog


def load(path):
    p=Path(path)
    return parse_json(read_file(p.parent,p.name))


def native_operation(args,driver=None):
    from .drivers import connect
    command=args['command'];root=args['root']
    config=load(args['config']) if command in {'inspect','prepare'} else workflow.load_plan(args['plan'])[0]['target']
    workflow.validate(config)
    driver=driver or connect(config['product'],args.get('credential_ref'))
    try:
        if command=='inspect':
            metadata,files=workflow.observe(root,config,driver,verify_version=False)
            if args.get('output'):
                bundle=make_bundle(config['product'],'native-read-'+digest(metadata)[:20],files,
                    load(args['requirements']) if args.get('requirements') else [],
                    source={'native_observation':True},missing=['Unselected dependencies not captured','Physical verification not performed'])
                write_bundle(args['output'],bundle)
            return metadata
        if command=='prepare':
            return workflow.prepare(root,config,parse_json(args['value']),args['reason'],
                load(args['requirements']) if args.get('requirements') else [],args['output'],driver)
        if command=='apply':
            return workflow.apply(args['plan'],args['expect_plan'],root,driver,exclusive=args.get('exclusive',False))
        return workflow.reconcile(args['plan'],root,driver,writer_stopped=args.get('writer_stopped',False))
    finally:
        if config['product']=='creo':driver.connection.Disconnect(10)


def public_result(result):
    # Bytes stay in the local journal/capture, not terminal output.
    return {k:v for k,v in result.items() if k!='after_files'}


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv==['_worker']:
        try:result=public_result(native_operation(parse_json(sys.stdin.buffer.read(1024*1024))))
        except Fault as exc:print(canonical({'error':exc.as_dict()}));return 1
        except Exception:print(canonical({'error':{'code':'native_or_io_error','message':'Native operation failed; inspect the local receipt before retry'}}));return 1
        print(canonical(result));return 0
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('catalog')
    for name in ['inspect','prepare','apply','reconcile']:
        q=sub.add_parser(name);q.add_argument('--root',required=True)
        q.add_argument('--credential-ref');q.add_argument('--timeout',type=int,default=120)
        if name in {'inspect','prepare'}:
            q.add_argument('--config',required=True);q.add_argument('--requirements');q.add_argument('--output',required=name=='prepare')
        else:q.add_argument('--plan',required=True)
        if name=='prepare':q.add_argument('--value',required=True,help='JSON scalar');q.add_argument('--reason',required=True)
        if name=='apply':q.add_argument('--expect-plan',required=True);q.add_argument('--exclusive',action='store_true')
        if name=='reconcile':q.add_argument('--writer-stopped',action='store_true')
    q=sub.add_parser('evidence');q.add_argument('--root',required=True);q.add_argument('--plan',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('script-prepare')
    for n in ['root','config','expected','value','reason','output']:q.add_argument('--'+n,required=True)
    q.add_argument('--requirements')
    q=sub.add_parser('script-collect')
    for n in ['root','package','output']:q.add_argument('--'+n,required=True)
    q=sub.add_parser('publish')
    for n in ['bundle','url','token-file','state','change','key']:q.add_argument('--'+n,required=True)
    q.add_argument('--version',type=int,required=True)
    a=vars(p.parse_args(argv));command=a['command']
    try:
        if command=='catalog':result=catalog()
        elif command in {'inspect','prepare','apply','reconcile'}:
            require(1<=a['timeout']<=300,'invalid_input','Native timeout must be 1–300 seconds')
            try:
                child=subprocess.run([sys.executable,'-B','-m','gantry.native','_worker'],
                    input=canonical(a).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=a['timeout'])
                result=parse_json(child.stdout)
            except subprocess.TimeoutExpired:
                result={'status':'unknown','error':'native_timeout',
                    'message':'Client stopped. CAD may still be processing. Do not retry; confirm it stopped before reconcile.'}
            if 'error' in result:print(canonical(result));return 1
        elif command=='evidence':
            write_bundle(a['output'],workflow.evidence(a['plan'],a['root']));result={'bundle':a['output']}
        elif command=='script-prepare':
            from .scripts import prepare_script
            result=prepare_script(a['root'],load(a['config']),parse_json(a['expected']),parse_json(a['value']),a['reason'],
                load(a['requirements']) if a.get('requirements') else [],a['output'])
        elif command=='script-collect':
            from .scripts import collect_script
            write_bundle(a['output'],collect_script(a['package'],a['root']));result={'bundle':a['output']}
        else:
            from ..client import Client
            from ..integrations.publication import publish
            token=Path(a['token_file']).resolve()
            require(not token.is_relative_to(Path(a['bundle']).resolve()),'credential_detected','Token must be outside capture')
            result=publish(Client(a['url'],token.read_text().strip()),a['state'],a['change'],a['version'],a['bundle'],a['key'])
        print(json.dumps(result,indent=2));return 0
    except Fault as exc:print(canonical({'error':exc.as_dict()}));return 1
    except (OSError,ValueError,KeyError,TypeError):
        print(canonical({'error':{'code':'invalid_input_or_io','message':'Check local paths and input; no blind write retry'}}));return 1


if __name__=='__main__':sys.exit(main())
