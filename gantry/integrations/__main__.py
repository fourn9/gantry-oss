"""Capture selected external records locally, then publish a reviewed immutable bundle."""
import argparse
import json
import sys
from pathlib import Path
from ..model import Fault
from .bundle import make_bundle, write_bundle, read_bundle, read_file
from .transport import parse_json


def load(path,default=None):
    if path is None: return default
    p=Path(path); return parse_json(read_file(p.parent,p.name))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('catalog')
    pull=sub.add_parser('pull',help='Read one explicit remote object/window; never remote writes')
    pull.add_argument('--config',required=True)
    local=sub.add_parser('capture',help='Preserve explicitly selected saved files')
    local.add_argument('--provider',required=True); local.add_argument('--root',required=True)
    local.add_argument('--path',action='append',required=True); local.add_argument('--cells',help='JSON worksheet -> cell addresses')
    for cmd in (pull,local):
        cmd.add_argument('--source-id',required=True); cmd.add_argument('--output',required=True)
        cmd.add_argument('--requirements',help='JSON array of requirement_id/revision_id references')
        cmd.add_argument('--select',help='JSON filename -> JSON pointers; original bytes remain saved')
    inspect=sub.add_parser('inspect'); inspect.add_argument('--bundle',required=True)
    pub=sub.add_parser('publish')
    for name in ('bundle','url','token-file','state-id','change-id','key'): pub.add_argument('--'+name,required=True)
    pub.add_argument('--version',type=int,required=True)
    args=p.parse_args(argv)
    try:
        if args.action=='catalog':
            from .catalog import catalog
            result=catalog()
        elif args.action=='inspect': result=read_bundle(args.bundle)['manifest']
        elif args.action=='publish':
            from ..client import Client
            from .publication import publish
            result=publish(Client(args.url,Path(args.token_file).read_text().strip()),args.state_id,args.change_id,
                           args.version,args.bundle,args.key)
        else:
            refs=load(args.requirements,[]); selectors=load(args.select,{})
            if args.action=='pull':
                from .providers import fetch
                cap=fetch(load(args.config))
                name='response.bin' if cap['provider']=='google-drive' else 'response.json'
                bundle=make_bundle(cap['provider'],args.source_id,{name:cap['raw']},refs,selectors,
                    source={**cap['source'],'revision_semantics':cap['revision_semantics'],'continuation':cap['continuation']},
                    missing=cap['missing'],source_revision=cap['source_revision'])
            else:
                from .local import capture_exports
                bundle=capture_exports(args.provider,args.source_id,args.root,args.path,refs,selectors,load(args.cells))
            write_bundle(args.output,bundle)
            result={'bundle':str(Path(args.output).absolute()),'provider':bundle['manifest']['provider'],
                    'files':len(bundle['files']),'missing':bundle['manifest']['missing'],'published':False}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except Fault as exc:
        print(json.dumps({'error':exc.code,'message':exc.message}),file=sys.stderr);return 1
    except (OSError,ValueError,TypeError,KeyError):
        print(json.dumps({'error':'invalid_input','message':'Check paths and bounded JSON configuration; no credentials logged'}),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
