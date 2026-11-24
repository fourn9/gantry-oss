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
