"""Opt-in customer inference over a bounded, saved onboarding context.

No automatic provider selection, no project execution and no API-key fallback.
Uses existing inference journals so reconnecting cannot silently repeat a model call.
"""
import base64
import hashlib
from pathlib import Path
from .model import digest,require
from .contracts import validate
from .onboarding_contracts import PROPOSAL
from .workspace import save,load,locked,private_dir

TEXT_EXT={'.md','.txt','.py','.rs','.c','.cpp','.h','.hpp','.js','.ts','.toml','.yaml','.yml','.json','.xml','.csv'}

def context_for(client,d):
    snippets=[];omitted=[];remaining=160000
    for path,info in sorted(d['manifest'].items()):
        if Path(path).suffix.lower() not in TEXT_EXT or info['size']>24000 or info['size']>remaining:
            omitted.append(path);continue
        r=client.call('read_artifact_chunk',{'revision_id':d['snapshot'],'path':path,'index':0})
        raw=base64.b64decode(r['content'],validate=True)
        require(hashlib.sha256(raw).hexdigest()==info['hash'],'integrity_error','Saved source hash mismatch')
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError:omitted.append(path);continue
        if '\0' in text:omitted.append(path);continue
        snippets.append({'path':path,'hash':info['hash'],'text':text});remaining-=len(raw)
    return {'task':'Prepare this existing project for its first shared work. Do not execute or edit files.',
        'goal':d['goal'],'snapshot':d['snapshot'],'hierarchy':d['hierarchy'],'manifest':d['manifest'],
        'answers':d['answers'],'corrections':d['corrections'],'known_questions':d['questions'],
        'reserved_question_ids':[q['id'] for q in d['discovery']['questions']],
        'source_text':snippets,'metadata_only_paths':omitted,'authority':d['agent_contract']['authority'],
        'instructions':'Return the proposal schema. Cite exact file hashes. Keep question IDs stable for the same ambiguity; never reuse reserved_question_ids. '
            'Do not ask answered questions again when their evidence and meaning are unchanged. '
            'Keep component IDs stable. Folder grouping is provisional. Preserve corrections. State missing native tool interpretation. '
            'Extract useful context but do not turn file assertions into approved requirements or verified results. '
            'Use inferred for engineering interpretations, observed only for directly quoted source statements. '
            'Suggest a useful first work and ask only blocking ambiguities for that work. No organization roster is required.'}

def analyze(client,onboarding_id,journal,infer):
    root=private_dir(Path(journal).absolute())
    binding={'endpoint':getattr(client,'url','local'),'actor':client.call('identity')['id']}
    with locked(root/'analysis.lock'):
        path=root/'submission.json'
        if path.exists():
            saved=load(path);require(saved['onboarding_id']==onboarding_id,'conflict','Journal belongs to another onboarding')
            require(saved['binding']==binding,'scope_denied','Journal belongs to another identity or server')
            if saved.get('result'):return saved['result']
            current=client.call('get_onboarding',{'onboarding_id':onboarding_id})
            require('receipt' in saved or (current['snapshot']==saved['snapshot'] and current['version']==saved['version']),
                    'stale_basis','Sources or human answers changed; preserve this attempt and use a fresh analysis journal')
        else:
            d=client.call('get_onboarding',{'onboarding_id':onboarding_id})
            require(d['status']=='draft','invalid_state','Project setup already completed')
            saved={'binding':binding,'onboarding_id':d['id'],'version':d['version'],'snapshot':d['snapshot'],'context':context_for(client,d)}
            saved['key']='onboard-analysis:'+digest([binding,d['id'],d['version']])
            save(path,saved)
        if 'receipt' not in saved:
            saved['receipt']=infer(saved['context'],PROPOSAL,root/'inference')
            validate(saved['receipt']['output'],PROPOSAL);save(path,saved)
        result=client.call('propose_onboarding',{'onboarding_id':onboarding_id,'version':saved['version'],
            'snapshot':saved['snapshot'],'proposal':saved['receipt']['output']},saved['key'])
        saved['result']={'onboarding_id':onboarding_id,'version':result['version'],
            'status':'proposal_saved','provider':saved['receipt'].get('provider',{}),'project_executed':False}
        save(path,saved);return saved['result']
