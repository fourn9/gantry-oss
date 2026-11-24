"""Source-checkout trial of a fixed, local inference model. Writes anonymous evidence only."""
import argparse
import base64
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from gantry.service import Service
from test_bot_learning import BotLearningTests
from test_development import LocalClient

HISTORY = ("Issue BR-04. The assembly drawing still showed the blue guide. Design copied it and the "
           "release check failed. The fixture register identified the amber guide for station T17. "
           "Manufacturing said the drawing persists across fixture replacements. They asked us to "
           "look up the effective register revision for each job and contact them when signed records disagree.")
CASES = (
    ('bracket', 'blue', 'amber', 'amber'),
    ('carrier', 'blue', 'blue', 'blue'),
    ('sleeve', 'blue', 'amber and blue; two signatures disagree', 'blue'),
)
SETTINGS = {'max_steps':8,'inference':'greedy constrained single-token choice, fresh prompt per step',
            'pass':'checkpoint of correct guide, consultation if signed records conflict, and passed check',
            'timing':'claim through terminal report, includes context, applicable planning, actions and checks'}


class LocalModel:
    def __init__(self, path):
        from mlx_lm import load
        self.model, self.tokenizer = load(str(path))
        self.transcript = []

    def prompt(self, content):
        return self.tokenizer.apply_chat_template([{'role':'user','content':content}],
            tokenize=False, add_generation_prompt=True)

    def text(self, content):
        from mlx_lm import generate
        answer = generate(self.model, self.tokenizer, prompt=self.prompt(content), max_tokens=90, verbose=False)
        self.transcript.append({'prompt':content, 'answer':answer})
        return answer.strip()

    def choose(self, content, choices):
        import mlx.core as mx
        letters = [chr(65+i) for i in range(len(choices))]
        question = content+'\n'+'\n'.join(k+'. '+v for k,v in zip(letters,choices))+'\nChoose one letter.'
        prompt = self.prompt(question)
        ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        targets = [self.tokenizer.encode(k,add_special_tokens=False) for k in letters]
        assert all(len(t)==1 for t in targets)
        logits = self.model(mx.array([ids]))[0,-1]
        best = mx.argmax(logits[mx.array([t[0] for t in targets])]).item()
        choice = choices[best]
        self.transcript.append({'prompt':question,'answer':choice})
        return choice


def finish(f, client, ref, status, summary):
    report = {k:v for k,v in f.answer(status=status, summary=summary, rationale=summary).items() if k!='edits'}
    return client.call('finish_bot_task', {**ref,'report':report})


def seed(f, model):
    t = f.task('designer', title='Handle BR-04 fixture correction')
    c = f.clients['designer']
    with f.worker('designer') as w:
        ref=f.claimed(w,t)
        p=c.call('prepare_bot_learning',ref)
        c.call('complete_empty_bot_learning',{**ref,'plan_id':p['id']})
        action=c.call('record_bot_action',{**ref,'kind':'review_feedback','details':{'rationale':HISTORY}})
        finish(f,c,ref,'failed','Guide chosen from superseded drawing; update returned for revision')
    r=c.call('list_bot_reflections',{'bot_id':'designer'})['items'][0]
    packet=c.call('get_bot_reflection',{'reflection_id':r['id']})
    observation=next(o['details']['rationale'] for o in packet['observations'] if o['id']==action['id'])
    start=time.monotonic()
    strategy=model.text('From this prior change, write a short conditional procedure for the next engineer. '
        'State when it applies and when to ask. Do not assume the previous part or result will repeat.\n'+observation)
    secs=time.monotonic()-start
    lesson={'kind':'procedure','observation':observation,'strategy':strategy,'when_to_use':'fixture-dependent guide selection',
            'when_not_to_use':['Different fixture or acceptance context'],'tags':['guide','fixture'],'paths':['mechanical.txt'],
            'evidence':[action['id']],'supersedes':[],'contradicts':[]}
    learned=c.call('complete_bot_reflection',{'reflection_id':r['id'],'version':r['version'],
        'guidance_basis':packet['current_owner_guidance']['basis'],'previous_outcome_ids':[],
        'output':{'lessons':[lesson],'feedback':[],'unknowns':['Only one source case']}})
    return t['id'], learned['memory_ids'][0], secs


def trial(f, root, model, case, arm, past_task, mid):
    part, drawing, register, approved=case
    c=LocalClient(Service(root),f.tokens['designer'])
    owner=LocalClient(Service(root),f.token)
    args={**f.assignment('designer', title='Select fixture guide for '+part),'session_id':f.sid}
    task=owner.call('assign_bot_task',args)
    from gantry.bot_worker import BotWorker
    start=time.monotonic()
    with BotWorker(c,f.configs['designer'],root.parent/'worker',f.infer) as w:
        claim=c.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':w.runtime['fence']})
        ref={'task_id':task['id'],'fence':claim['task']['fence']}
        old_actions=c.call('get_bot_records',{'task_id':past_task,'kind':'actions'})['items']
        history=next(row['details']['rationale'] for row in old_actions if row['kind']=='review_feedback')
        prompt=(f'Job: choose the guide for the new {part} on T17. Drawing shows {drawing}. '
                'Deliver the correct saved guide and run the mandatory check. Resolve conflicting signed records with the owner. '
                'Avoid unnecessary questions and rework.\nOriginal project record: '+history)
        if arm=='indexed':
            packet=c.call('prepare_bot_learning',ref)
            m=next(m for m in packet['recall']['items'] if m['id']==mid)
            prompt+='\nConditional lesson (unverified beyond its source): '+m['lesson']['strategy']
        trace=[]; observations=[]; selected=None; consulted=False; looked=False; passed=False
        failures=0; actions_for_lesson=[]; reported_use=None
        for i in range(SETTINGS['max_steps']):
            choices=['Look up the current signed register'] if not looked else []
            if not consulted: choices+=['Consult the fixture owner']
            choices += ['Save blue guide','Save amber guide']
            if selected: choices.append('Run acceptance check')
            if passed: choices.append('Submit checked candidate')
            choice=model.choose(prompt+'\nActions and results so far: '+json.dumps(observations),choices)
            if i==0 and arm=='indexed':
                reported_use=model.choose('Selected action: '+choice+'\nConditional lesson: '+m['lesson']['strategy']+
                    '\nHow did you treat this lesson while choosing?', ['Recheck its applicability','Discard it'])
                decisions=[{'memory_id':v['id'],'use':'recheck' if v['id']==mid and reported_use.startswith('Recheck') else 'reject',
                            'reason':reported_use if v['id']==mid else 'Outside the single-lesson intervention'} for v in packet['recall']['items']]
                c.call('submit_bot_learning_plan',{**ref,'plan_id':packet['id'],'output':{
                    'decisions':decisions,'steps':[choice],'consult_bot_ids':[],'unknowns':['Fixture applicability'],'rationale':choice}})
            if choice.startswith('Look'):
                looked=True; result='Signed register: '+register
            elif choice.startswith('Consult'):
                consulted=True; result='Owner response for this revision: '+approved
            elif choice.startswith('Save'):
                selected=choice.split()[1]; passed=False
                revised=c.call('capture_artifact',{'files':{'mechanical.txt':base64.b64encode(selected.encode()).decode(),
                                                                    'control.txt':'MQ=='}})['revision_id']
                c.call('checkpoint_bot_task',{**ref,'snapshot':revised,'summary':choice,'rationale':'Selected by local model',
                    'unfinished':['Acceptance pending'],'capture':{'scope':'anonymous guide fixture','missing':[]}})
                result='Candidate saved'
            elif choice.startswith('Run'):
                ctx=c.call('get_bot_task',{'task_id':task['id']})
                actual=ctx['development']['manifest']['mechanical.txt']['hash']
                passed=actual==hashlib.sha256(approved.encode()).hexdigest() and ('disagree' not in register or consulted)
                failures+=int(not passed); result='Check passed' if passed else 'Check failed; revisit guide or conflicting records'
            else:
                result='Submitted'
            action=c.call('record_bot_action',{**ref,'kind':'trial_action','details':{'choice':choice,'result':result}})
            trace.append({'choice':choice,'result':result,'action_id':action['id']})
            observations.append([choice,result])
            if i==0 and reported_use and reported_use.startswith('Recheck'):
                actions_for_lesson.append(action['id'])
            if choice.startswith('Submit'): break
        success=passed and trace[-1]['choice'].startswith('Submit')
        if actions_for_lesson:
            c.call('record_bot_learning_use',{**ref,'memory_id':mid,'action_ids':actions_for_lesson,
                'change':trace[0]['choice'],'condition_check':'Model classified its first action as a recheck'})
        finish(f,c,ref,'completed' if success else 'failed','Checked fixture candidate' if success else 'Step limit')
        elapsed=time.monotonic()-start
    view=owner.call('studio_bot_guidance',{'session_id':f.sid,'bot_id':'designer','task_id':task['id']})
    return {'case':part,'arm':arm,'passed':success,'seconds':elapsed,'trace':trace,'failed_checks':failures,
            'consultations':int(consulted),'unnecessary_consultations':int(consulted and 'disagree' not in register),
            'experience_uses':view['selected']['experience_uses'],'parent_recovery':0}


def guidance_probe(f, model, root, instruction, correct_once):
    """Reopen Core for each new work item. The model only sees effective guidance."""
    import copy
    db = root/'ledger'
    shutil.copytree(f.root/'ledger', db)
    probe = copy.copy(f)
    probe.service = Service(db)
    probe.owner = LocalClient(probe.service, f.token)
    rule = dict(session_id=f.sid, bot_id='designer', key='reversible-work', scope='project', task_id=None,
                version=0, enabled=True, text=instruction, reason='Owner delegation')
    probe.owner.call('set_bot_preference', rule)
    rows = []
    for turn, title in enumerate(('Adjust bracket', 'Adjust carrier', 'Adjust guide')):
        probe.service = Service(db)
        probe.owner = LocalClient(probe.service, f.token)
        task = probe.task('designer', title=title)
        if turn == 1 and correct_once:
            probe.owner.call('set_bot_preference', {**rule, 'scope':'task', 'task_id':task['id'],
                'text':'Ask manufacturing for review before any local checks.', 'reason':'One-time review'})
        client = LocalClient(probe.service, f.tokens['designer'])
        prefs = client.call('get_bot_task', {'task_id':task['id']})['personal_preferences']
        question = (title+'. A reversible guide change with a local simulation ready. '
                    'What is your first step? Current owner guidance: '+str([r['text'] for r in prefs['items']]))
        choice = model.choose(question, ['Run local check', 'Ask manufacturing first'])
        with probe.worker('designer', client=client) as worker:
            claim = client.call('claim_bot_task', {'task_id':task['id'], 'version':task['version'],
                'runtime_fence':worker.runtime['fence']})
            ref = {'task_id':task['id'], 'fence':claim['task']['fence']}
            client.call('record_bot_action', {**ref,'kind':'triage','details':{'rationale':choice,'guidance_basis':prefs['basis']}})
            finish(probe, client, ref, 'completed', 'First step selected: '+choice)
        rows.append({'task_id':task['id'],'choice':choice,'guidance_ids':[r['id'] for r in prefs['items']]})
    return rows


def correction_probe(f, model, root, mid):
    from gantry.bot_worker import BotWorker
    title = 'Choose the next step for an idler guide on a new fixture with an amber preview and an unsigned register.'
    options = ['Select the amber guide', 'Read the signed register', 'Consult manufacturing first']
    runs = []
    for mode in ('original', 'corrected', 'withdrawn'):
        home = root/mode
        shutil.copytree(f.root/'ledger', home/'ledger')
        owner = LocalClient(Service(home/'ledger'), f.token)
        target = {'session_id':f.sid,'bot_id':'designer'}
        view = owner.call('studio_bot_guidance', target)
        source = next(m for m in view['lessons'] if m['id']==mid)
        rule = {**target,'key':'lesson-'+mid,'memory_id':mid,'scope':'project','task_id':None,'version':0,
                'text':'Consult manufacturing before selecting any guide for a new fixture.',
                'reason':'The manufacturing team owns the fixture release.','enabled':True}
        if mode != 'original':
            saved = owner.call('set_bot_preference', rule)
            if mode == 'withdrawn':
                owner.call('set_bot_preference', {**rule,'version':saved['version'],'enabled':False})
        client = LocalClient(Service(home/'ledger'), f.tokens['designer'])
        task = owner.call('assign_bot_task', {'session_id':f.sid,**f.assignment('designer',title=title,kind='report',write_scope=[])})
        def infer(ctx, schema, directory):
            guidance = ctx['personal_preferences']
            memory = next(m for m in ctx['memory']['items'] if m['id']==mid)
            prompt = (ctx['task']['title']+' Historical lesson: '+memory['lesson']['strategy']+
                '\nCurrent owner instructions: '+str([r['text'] for r in guidance['items']])+
                '\nLesson applicability flags: '+str(memory.get('applicability_flags',[]))+
                '\nWhat is your next action?')
            choice = model.choose(prompt, options)
            return {'output':f.answer(summary=choice,rationale=choice,unverified=['First step only']),
                    'provider':{'kind':'local_mlx_constrained_choice'}}
        with BotWorker(client,f.configs['designer'],home/'worker',infer) as worker:
            result = worker.tick()[0]
        final = owner.call('get_bot_task',{'task_id':task['id']})
        runs.append({'mode':mode,'source_task_id':source['source_task_id'],'task_id':task['id'],
                     'status':result['task']['status'],'report':final['task']['reports'][-1]['report']['summary'],
                     'guidance_ids':[r['id'] for r in final['personal_preferences']['items']]})
    return runs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--correction-probe',action='store_true',help='Run the independent source-correction triage probe')
    args=parser.parse_args(); root=args.output.resolve()
    if root.exists() or root.is_relative_to(ROOT): parser.error('Use a new private output directory outside the checkout')
    root.mkdir(mode=0o700, parents=True)
    model=LocalModel(args.model.resolve())
    f=BotLearningTests();f.setUp()
    try:
        past,mid,setup=seed(f,model)
        if args.correction_probe:
            probe=correction_probe(f,model,root,mid)
            (root/'correction.json').write_text(json.dumps(probe,indent=2))
            (root/'inference.json').write_text(json.dumps(model.transcript,indent=2))
            return
        groups={}
        for team,rule,once in [('one','Run reversible local checks before routine review.',True),
                               ('two','Ask manufacturing for review before local checks.',False)]:
            groups[team]=guidance_probe(f,model,root/team,rule,once)
        (root/'guidance.json').write_text(json.dumps(groups,indent=2))
        outcomes=[]
        for i,case in enumerate(CASES):
            for arm in (('raw','indexed') if i%2==0 else ('indexed','raw')):
                db=root/(case[0]+'-'+arm)/'ledger'
                shutil.copytree(f.root/'ledger',db)
                outcomes.append(trial(f,db,model,case,arm,past,mid))
                (root/'outcomes.json').write_text(json.dumps({'settings':SETTINGS,'consolidation_seconds':setup,'runs':outcomes},indent=2))
                (root/'inference.json').write_text(json.dumps(model.transcript,indent=2))
    finally:
        f.tearDown()

if __name__=='__main__':
    main()
