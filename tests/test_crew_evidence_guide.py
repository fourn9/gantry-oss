import hashlib
import json
import unittest

from gantry.bot_worker import environment_manifest
from gantry.model import Fault


class EvidenceGuideTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'source': {'path':'register.json','pointer':'/name'}, 'candidate':'part.txt','check_tool':'test'}
        self.raw = '{"name":"north"}'
        self.files = {'register.json': self.raw,'part.txt':'pending'}
        self.full = {'task':{'id':'task1','kind':'develop','write_scope':['part.txt'],'completion':['Check the selected guide']},
                     'development':{'state':{'id':'s1'},'manifest':{p:{'hash':self.hash(s)} for p,s in self.files.items()}},
                     'consultations':[],'actions':[]}
    def hash(self, s):
        return hashlib.sha256(s.encode()).hexdigest()
    def add(self, kind, args, result, state='s1'):
        if kind == 'tool':
            result.setdefault('check_definition','installed')
        self.full['actions'].insert(0, {'id':'r'+str(len(self.full['actions'])), 'kind':kind,'task_id':'task1','input_state':state,
            'details':{'arguments':json.dumps(args),'result':result}})
    def guide(self):
        from gantry.crew_progress import evidence_guide
        return evidence_guide(self.full,self.files,self.cfg,'installed')
    def read(self, value):
        self.add('inspect_json',self.cfg['source'],{'source':{'sha256':self.hash(self.raw),'path':'register.json'},
            'pointer':'/name','value':value,'next_offset':None})
    def test_read_requires_exact_authorized_bytes_and_survives_unrelated_checkpoint(self):
        self.read('invented')
        self.assertIsNone(self.guide()['observed'])
        self.read('north')
        self.assertEqual(self.guide()['observed']['value'],'north')
        self.full['development']['state']['id']='s2'
        self.assertEqual(self.guide()['observed']['value'],'north')
        self.files['register.json']='{"name":"south"}'
        self.assertIsNone(self.guide()['observed'])
    def test_newer_failure_and_changed_state_do_not_inherit_success(self):
        self.read('north')
        self.add('tool',{'name':'test'},{'exit_code':0,'output_artifact':'a'})
        self.assertEqual(self.guide()['check']['status'],'passed')
        self.add('tool',{'name':'test'},{'exit_code':1,'output_artifact':'b'})
        self.assertEqual(self.guide()['check']['status'],'failed')
        self.full['development']['state']['id']='s2'
        self.assertEqual(self.guide()['check']['status'],'not_observed')
    def test_workflow_is_pinned_and_never_selects_a_design(self):
        cfg={'backend':'external_agent','name':'fixture','agent_loop':True}
        self.assertNotEqual(environment_manifest(cfg),environment_manifest({**cfg,'evidence_guide':self.cfg}))
        self.read('north')
        self.assertIn('edit',self.guide()['focus_actions'])
        self.assertIn('ask',self.guide()['focus_actions'])
        self.assertNotIn('content',self.guide())
        self.full['task']['write_scope']=[]
        self.assertIsNone(self.guide())
    def test_peer_report_requires_exact_request_and_preserves_limitations(self):
        request={'task_id':'other','pointer':'/task/reports/1/report'}
        self.full['consultations']=[{'id':'q','blocking':True,'status':'answered','response_report':{'request':request,'state_id':'s1'}}]
        self.add('inspect',{**request,'pointer':'/task/reports/0/report'},{'value':{'summary':'wrong'}})
        self.assertEqual(self.guide()['focus_actions'],['inspect'])
        self.add('inspect',request,{**request,'next_offset':None,'value':{'status':'completed','summary':'north','unverified':['load']}})
        guide=self.guide()
        self.assertEqual(guide['consultation']['report']['unverified'],['load'])
        self.assertEqual(guide['focus_actions'],['resolve'])

    def test_menu_escape_keeps_every_original_action_and_order(self):
        from gantry.crew_progress import choose_focused
        menus = []
        def choose(prompt, options):
            menus.append(options)
            return options[-1]
        options = ['Save north','Ask a peer','Reread']
        selected = choose_focused(choose, 'fixture', options, dict(zip(options,['edit','ask','inspect_json'])),
                                  {'focus_actions':['edit','ask']})
        self.assertEqual((menus[0][:-1],menus[1],selected),(options[:2],options,'Reread'))
    def test_guide_rejects_undeclared_tool_and_unsafe_paths(self):
        from gantry.crew_progress import validate_guide
        config = {'workflow':'bot_development','agent_loop':True,'evidence_guide':self.cfg,'local_tools':{}}
        with self.assertRaises(Fault):
            validate_guide(config)
        config['local_tools']['test']={}
        validate_guide(config)
        self.cfg['source']['path']='../private.json'
        with self.assertRaises(Fault):
            validate_guide(config)
    def test_large_edit_and_stale_check_keep_latest_candidate_unverified(self):
        self.read('north')
        self.add('edit',{'content':'x'*20000},{'path':'part.txt','hash':self.hash('pending')})
        self.add('tool',{'name':'test'},{'exit_code':0,'output_artifact':'r'},state='older')
        guide=self.guide()
        self.assertEqual(guide['focus_actions'],['tool'])
        self.assertEqual(guide['check']['status'],'not_observed')
        self.assertEqual(guide['previous_check']['state_id'],'older')

    def test_setup_accepts_only_valid_guidance_before_manifest_is_pinned(self):
        from gantry.crew_setup_client import _runtime_template
        template={'name':'guide role','local_tools':{'test':{}},'evidence_guide':self.cfg}
        self.assertEqual(_runtime_template('codex-subscription',template)['evidence_guide'],self.cfg)
        with self.assertRaises(Fault):
            _runtime_template('codex-subscription',{**template,'local_tools':{}})

    def test_failed_receipt_demotes_only_literal_noop_and_allows_explicit_retry(self):
        from gantry.crew_progress import choose_focused
        menu = ['write x','write y','ask']
        kinds = {'write x':'edit','write y':'edit','ask':'ask'}
        guide = {'focus_actions':['edit','ask'],'candidate_hash':self.hash('x'),'check':{'status':'failed'}}
        writes = {'write x':self.hash('x'),'write y':self.hash('y')}
        menus=[]
        def choose(prompt, options):
            menus.append(options)
            return options[-1] if len(menus)==1 else options[0]
        self.assertEqual(choose_focused(choose,'fixture',menu,kinds,guide,writes),'write x')
        self.assertEqual(menus[0][:-1],['write y','ask'])
        self.assertEqual(menus[1],menu)
        guide['check']['status']='not_observed'
        choices=[]
        choose_focused(lambda p,o: choices.extend(o) or o[0], 'fixture', menu, kinds, guide, writes)
        self.assertEqual(choices,menu)

    def test_changed_tool_definition_invalidates_success_even_on_same_file_state(self):
        self.read('north')
        self.add('tool',{'name':'test'},{'exit_code':0,'output_artifact':'r','check_definition':'superseded'})
        guide = self.guide()
        self.assertEqual(guide['check']['status'],'not_observed')
        self.assertFalse(guide['previous_check']['same_definition'])

    def test_sensitive_observation_is_omitted_from_decision_projection(self):
        marker='-----BEGIN '+'PRIVATE KEY-----'
        self.raw=json.dumps({'name':marker})
        self.files['register.json']=self.raw
        self.full['development']['manifest']['register.json']['hash']=self.hash(self.raw)
        self.read(marker)
        self.assertIsNone(self.guide()['observed'])

    def route(self):
        self.cfg['consultation_policy'] = {'peer':'control','sources':[self.cfg['source'],{'path':'register.json','pointer':'/approved'}],
                                           'allowed_values':['north','south']}
        return self.guide()

    def register(self, obj):
        self.raw=json.dumps(obj)
        self.files['register.json']=self.raw
        self.full['development']['manifest']['register.json']['hash']=self.hash(self.raw)

    def test_route_reads_saved_values_and_preserves_explicit_reviews(self):
        self.register({'name':'north','approved':'north'})
        guide=self.route()
        self.assertEqual(guide['routing']['status'],'consistent')
        self.assertNotIn('ask',guide['focus_actions'])
        self.full['consultations']=[{'id':'other','blocking':True,'status':'open'}]
        self.assertEqual(self.route()['phase'],'await_answer')

    def test_contradictory_missing_and_untrusted_sources_require_peer(self):
        for data, status in [({'name':'north','approved':'south'},'conflict'),({'name':'north'},'missing'),
                             ({'name':'new','approved':'new'},'missing')]:
            self.register(data)
            guide=self.route()
            self.assertEqual(guide['routing']['status'],status)
            self.assertEqual(guide['focus_actions'],['ask'])
        del self.files['register.json']
        self.assertEqual(self.route()['routing']['status'],'missing')
        del self.full['development']['manifest']['register.json']
        self.assertEqual(self.route()['focus_actions'],['ask'])

    def test_resolved_question_only_counts_for_current_peer_basis_and_answer(self):
        self.register({'name':'north','approved':'south'})
        basis=self.route()['routing']['basis']
        request={'task_id':'other','pointer':'/task/reports/0/report'}
        question={'id':'q','blocking':True,'status':'resolved','to_bot_id':'wrong','consultation_basis':basis,
                  'answer_id':'a','resolution':{'evidence':['a']},'response_report':{'request':request,'state_id':'s1'}}
        self.full['consultations']=[question]
        self.add('inspect',request,{**request,'value':{'status':'completed','summary':'south'}})
        self.assertEqual(self.route()['focus_actions'],['ask'])
        question['to_bot_id']='control'
        question['resolution']['evidence']=[]
        self.assertEqual(self.route()['focus_actions'],['ask'])
        question['resolution']['evidence']=['a']
        self.assertFalse(self.route()['routing']['consulted'])
        question['reviewed_basis']=basis
        self.assertTrue(self.route()['routing']['consulted'])
        self.full['development']['state']['id']='candidate-only'
        self.assertTrue(self.route()['routing']['consulted'])
        self.register({'name':'south','approved':'north'})
        self.assertFalse(self.route()['routing']['consulted'])
