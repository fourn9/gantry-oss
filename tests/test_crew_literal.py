import unittest

from gantry.model import Fault


class HandoffTests(unittest.TestCase):
    def test_contract_requires_same_source_bytes_after_review(self):
        from gantry.crew_literal import selected_value
        source = {'path':'approval.json','pointer':'/approved'}
        observation = {**source,'sha256':'sha','value':'north'}
        route = {'basis':'basis','peer':'integration','status':'conflict','consulted':True}
        question = {'to_bot_id':'integration','status':'resolved','reviewed_basis':'basis','answer_id':'answer',
                    'resolution':{'evidence':['answer']},'reviewed_observation':observation}
        full = {'development':{'manifest':{'approval.json':{'hash':'sha'}}},'consultations':[question]}
        self.assertEqual(selected_value(full,route,source,['north','south']),'north')
        full['development']['manifest']['approval.json']['hash']='changed'
        self.assertIsNone(selected_value(full,route,source,['north','south']))

    def test_conditional_finish_requires_identical_check_and_discussion(self):
        from gantry.crew_literal import continuation
        full={'task':{'id':'t','attempt':1,'discussion_version':4},'development':{'state':{'id':'s'}},'messages':[]}
        guide={'check':{'status':'passed','action_id':'check'},'literal':{'matches':True}}
        token={'task':'t','attempt':1,'state':'s','discussion':4,'preferences':'p','check':'check',
               'report':{'summary':'covered','rationale':'r','unverified':['strength']}}
        self.assertEqual(continuation(token, full,guide,'p')['output']['action'],'finish')
        for field in ('state','discussion','attempt','preferences','check','task'):
            self.assertIsNone(continuation({**token,field:'other'}, full,guide,'p'))
        full['messages']=[{'blocking':True,'status':'open'}]
        self.assertIsNone(continuation(token, full,guide,'p'))

    def test_publisher_requires_approved_requester_and_category(self):
        from gantry.crew_literal import publication
        full={'task':{'kind':'report'},'response_request':{'from_bot_id':'design','consultation_basis':'basis'}}
        cfg={'source':{'path':'source.json','pointer':'/category'},
             'publish_observed':{'requester':'design','allowed_values':['north']}}
        read={'value':'north','action_id':'read','source_hash':'hash'}
        out=publication(full,cfg,read)
        self.assertEqual(out['observation']['action_id'],'read')
        self.assertEqual(out['summary'],'Report category: north')
        self.assertIsNone(publication(full,cfg,{**read,'value':'outside'}))
        full['response_request']['from_bot_id']='someone_else'
        self.assertIsNone(publication(full,cfg,read))

    def test_core_rejects_different_source_value_even_with_matching_claimed_read(self):
        import hashlib
        import json
        from types import SimpleNamespace
        from gantry.crew_literal import verify_report,summary
        raw=b'{"category":"north"}'
        h=hashlib.sha256(raw).hexdigest()
        src={'path':'source.json','pointer':'/category'}
        obs={**src,'action_id':'read','sha256':h,'value':'south'}
        task={'kind':'report','id':'peer','state_id':'s','reply_request_id':'q'}
        state={'bot_task_messages':{'q':{'consultation_basis':'basis','response_task_id':'peer'}},
               'bot_actions':{'read':{'kind':'inspect_json','task_id':'peer','input_state':'s',
                    'details':{'arguments':json.dumps(src),'result':{'pointer':'/category','value':'south',
                               'source':{'path':'source.json','sha256':h}}}}}}
        service=SimpleNamespace(_continuity_state=lambda *a:{'snapshot':'rev'},
              _manifest=lambda *a:{'source.json':{'hash':h,'size':len(raw)}},
              store=SimpleNamespace(verified_parts=lambda info:[raw]))
        report={'status':'completed','integrate_changes':[],'summary':summary(obs),'observation':obs}
        with self.assertRaises(Fault):
            verify_report(service,state,{},task,report)
        obs['value']='north'
        state['bot_actions']['read']['details']['result']['value']='north'
        report['summary']=summary(obs)
        verify_report(service,state,{},task,report)
        state['bot_actions']['read']['task_id']='stranger'
        with self.assertRaises(Fault):
            verify_report(service,state,{},task,report)

    def test_atomic_finish_rechecks_original_intent_state_and_attempt(self):
        import json
        from gantry.crew_literal import verify_submission
        fields={'summary':'tested','rationale':'within allowed load','unverified':['lifetime']}
        actual={**fields,'status':'completed','assignments':[],'integrate_changes':[]}
        task={'id':'t','attempt':1,'state_id':'state','discussion_version':2}
        receipt={'kind':'tool','task_id':'t','attempt':1,'input_state':'state','details':{
            'arguments':json.dumps({'name':'check','submit_on_pass':fields}),'result':{
            'exit_code':0,'output_artifact':'art','check_definition':'definition'}}}
        state={'bot_actions':{'check':receipt}}
        guard={'action_id':'check','discussion_version':2}
        verify_submission(state,task,actual,guard)
        for changed in ({'output_state':'other'},{'attempt':2},{'discussion_version':3}):
            with self.assertRaises(Fault):
                verify_submission(state,{**task,**changed},actual,guard)
        with self.assertRaises(Fault):
            verify_submission(state,task,{**actual,'unverified':[]},guard)
        receipt['details']['result']['exit_code']=1
        with self.assertRaises(Fault):
            verify_submission(state,task,actual,guard)

    def test_literal_guard_checks_raw_edit_and_replace_bytes_before_write(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from gantry.crew_runtime import _execute
        from gantry.service import Service  # Loads the command schemas used by a running Worker.
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp).resolve()
            h=lambda b:hashlib.sha256(b).hexdigest()
            saved={'register.json':b'{"a":"north","b":"north"}','candidate.txt':b'old'}
            for path,raw in saved.items():
                (work/path).write_bytes(raw)
            full={'task':{'id':'task','kind':'develop','write_scope':['candidate.txt']},
                  'development':{'state':{'id':'state'},'manifest':{p:{'hash':h(v),'size':len(v)} for p,v in saved.items()}},
                  'consultations':[],'actions':[]}
            src=lambda key:{'path':'register.json','pointer':'/'+key}
            cfg={'evidence_guide':{'source':src('a'),'candidate':'candidate.txt','check_tool':'test',
                'consultation_policy':{'peer':'peer','sources':[src('a'),src('b')],
                                       'allowed_values':['north','south'],'literal_source':src('release')}}}
            for action, fields in [('edit',{'content':'south'}),('replace',{'old_text':'old','new_text':'south'})]:
                with self.assertRaises(Fault) as ctx:
                    _execute(None,full,{},cfg,action,{'path':'candidate.txt','expected_hash':h(b'old'),**fields},work,None,'key')
                self.assertEqual(ctx.exception.code,'evidence_required')
                self.assertEqual((work/'candidate.txt').read_bytes(),b'old')

    def test_unapplied_candidate_defers_acceptance_but_allows_explicit_diagnosis(self):
        from gantry.crew_literal import check_arguments
        guide={'literal':{'matches':False},'check':{'name':'release'}}
        with self.assertRaises(Fault) as failure:
            check_arguments({'name':'release'},guide)
        self.assertEqual(failure.exception.code,'evidence_required')
        self.assertEqual(check_arguments({'name':'release','diagnostic_reason':'Measure the original baseline'},guide),
                         ({'name':'release'},True))
        self.assertEqual(check_arguments({'name':'other'},guide),({'name':'other'},False))
        with self.assertRaises(Fault):
            check_arguments({'name':'release','diagnostic_reason':'Inspect','submit_on_pass':{}},guide)

    def test_check_after_edit_requires_the_exact_checkpoint_and_edit(self):
        from gantry.crew_literal import continuation
        full={'task':{'id':'t','attempt':1,'discussion_version':2},'development':{'state':{'id':'new'}},'messages':[]}
        guide={'check':{'status':'not_observed','name':'check'},'literal':{'matches':True},'edit_action_id':'e'}
        token={'task':'t','attempt':1,'state':'new','discussion':2,'preferences':'p','edit':'e',
               'name':'check','report':{'summary':'done','rationale':'bound','unverified':['wear']}}
        self.assertEqual(continuation(token,full,guide,'p')['output']['action'],'tool')
        for field in ('state','edit','name','attempt','discussion','preferences'):
            self.assertIsNone(continuation({**token,field:'changed'},full,guide,'p'))
        self.assertIsNone(continuation(token,full,{**guide,'literal':{'matches':False}},'p'))
