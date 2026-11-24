"""Compare conditional peer consultation with the preceding retry-aware evidence guide."""
import argparse
import itertools
import json
import random
import subprocess
import sys
import time
from pathlib import Path

from worker_progress_trial import (BotLearningTests, CHECK, FrozenLesson, LocalModel, backend, checkpoint,
                                   environment_manifest, run, runtime_roots, seed)

POLICY = {'peer':'control','sources':[{'path':'control.txt','pointer':'/signed/'+field}
          for field in ('design','integration')],'allowed_values':['blue','amber']}
# Neither inference bridge receives the manufacturing decision before consultation or tool execution.
CASES = [
    ('bracket', 'consistent', {'design':'blue','integration':'blue'}, 'blue'),
    ('coupler', 'consistent', {'design':'amber','integration':'amber'}, 'amber'),
    ('shoe', 'conflict', {'design':'blue','integration':'amber'}, 'amber'),
    ('rail', 'conflict', {'design':'amber','integration':'blue'}, 'blue'),
    ('pawl', 'missing', {'design':'amber'}, 'blue'),
    ('sleeve', 'missing', {'integration':'blue'}, 'amber'),
]
SMOKE = ('diagnostic', 'conflict', {'design':'blue','integration':'amber'}, 'amber')


HELD_OUT = [
    ('hinge','consistent',{'design':'violet','integration':'violet'},'violet'),
    ('keeper','consistent',{'design':'teal','integration':'teal'},'teal'),
    ('platen','conflict',{'design':'white','integration':'teal'},'violet'),
    ('piston','conflict',{'design':'violet','integration':'white'},'white'),
    ('lever','missing',{'integration':'white'},'teal'),
    ('spindle','missing',{},'white')]


def fixture(row):
    name, condition, signed, release = row
    summary = release if condition == 'consistent' else '; '.join(field+' '+signed.get(field,'missing') for field in ('design','integration'))
    if condition == 'conflict':
        summary += '; current signatures disagree'
    return name, summary, release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--handoff',choices=['pilot','regression','held-out'],help='Compare the routed baseline with evidence-bound handoff')
    args = parser.parse_args()
    root = args.output.resolve()
    if (root.exists() or root.is_relative_to(Path(__file__).resolve().parents[1])
            or not args.smoke and not args.model):
        parser.error('Supply a fresh private output directory and a local model (or --smoke)')
    root.mkdir(mode=0o700, parents=True)
    start = time.perf_counter()
    model = None if args.smoke else LocalModel(args.model.resolve())
    load_seconds = time.perf_counter()-start
    f = BotLearningTests()
    f.setUp()
    try:
        past, mid, _ = seed(f, FrozenLesson())
        for role, config in f.configs.items():
            if role not in ('designer','control'):
                continue
            config.update(agent_loop=True, evidence_guide={'source':{'path':'control.txt','pointer':'/release' if role=='control' else '/register'}})
            if role == 'designer':
                config.update(local_tools={'release_check':{'argv':[str(Path(sys.base_prefix)/'bin'/'python3'),'-c',CHECK],
                              'timeout_seconds':10}}, sandbox=backend(), tool_runtime=runtime_roots())
                config['evidence_guide'].update(candidate='mechanical.txt',check_tool='release_check')
            f.owner.call('configure_bot_runtime', {'bot_id':role,'version':1,'principal_id':role,
                         'enabled':True,'environment':environment_manifest(config)})
        cases = [SMOKE] if args.smoke else CASES
        if args.handoff == 'pilot':
            cases = [SMOKE]
        policy = POLICY
        if args.handoff == 'held-out' and not args.smoke:
            cases = HELD_OUT
            policy = {**POLICY,'allowed_values':['teal','white','violet']}
        states = {r[0]: checkpoint(f,fixture(r),r[2]) for r in cases}
        groups = [(SMOKE,False,0,True)] if args.smoke else list(itertools.product(cases,(False,True),range(2),(False,True)))
        random.Random(2531).shuffle(groups)
        manifest = {'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).parent,text=True).strip(),
                    'study':args.handoff or 'routing', 'model_load_seconds':load_seconds,'states':states,'groups':groups,'limits':{'requester':8,'peer':4}}
        (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
        for i,(case,memory,rotation,routed) in enumerate(groups):
            n = len(model.transcript) if model else 0
            spec = {'enabled':routed or bool(args.handoff), 'handoff':routed and bool(args.handoff),'policy':policy,'require_peer':case[1]!='consistent'}
            row = run(f,model,root/str(i),fixture(case),states[case[0]],past,mid,memory,True,rotation,
                      smoke=args.smoke,guided=True,retry_aware=True,routing_study=spec)
            row.update(routed=routed,condition=case[1],model_calls=len(model.transcript)-n if model else 0)
            with (root/'runs.jsonl').open('a') as stream:
                print(json.dumps(row),file=stream)
            if model:
                (root/str(i)/'inference.json').write_text(json.dumps(model.transcript[n:]))
            print(i,case[0],routed,row['status'],row['passed'],round(row['seconds'],2),flush=True)
            if args.smoke:
                assert row['passed'] and row['peer_chain'],row
    finally:
        f.tearDown()


if __name__ == '__main__':
    main()
