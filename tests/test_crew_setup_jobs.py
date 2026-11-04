"""Owner-bound customer setup queue over a real transactional Core."""
import copy
import unittest
from concurrent.futures import ThreadPoolExecutor

from gantry.model import digest
from gantry.service import Service
from test_crew_setup import CrewSetupTests as Fixtures


class CrewSetupJobTests(unittest.TestCase):
    setUp=Fixtures.setUp
    tearDown=Fixtures.tearDown
    call=Fixtures.call
    artifact=Fixtures.artifact
    connect=Fixtures.connect
    policy=Fixtures.policy
    fault=Fixtures.fault
    imported=Fixtures.imported
    person=Fixtures.person
    setup=Fixtures.setup
    ref=Fixtures.ref
    proposal=Fixtures.proposal
    propose=Fixtures.propose
    grants=Fixtures.grants
    activate=Fixtures.activate

    def host(self, **extra):
        return self.call('register_crew_setup_host', {'host_id':'customer-host','instance_id':'process-one',
            'name':'Customer workstation','config_hash':digest('configuration'),
            'backend':'codex-subscription','tools':['read-source'], **extra})

    def request(self,d,action='analyze',**extra):
        if action=='start':
            extra.setdefault('session_version',self.call('development_state',{'session_id':d['session_id']})['session']['version'])
        return self.call('request_crew_setup_job', {**self.ref(d),'host_id':'customer-host',
            'config_hash':digest('configuration'),'action':action,**extra})

    def claim(self,instance='process-one'):
        return self.call('claim_crew_setup_job', {'host_id':'customer-host','instance_id':instance})['job']

    def finish(self,j,status='succeeded',**extra):
        return self.call('finish_crew_setup_job', {'host_id':j['host_id'],'instance_id':j['instance_id'],
            'job_id':j['id'],'status':status,'summary':'Customer setup completed.',**extra})

    def prepared(self,d):
        return {'proposal_hash':d['proposal']['hash'],'runtime_plan_hash':digest('runtime-plan'),
            'roles':[{'role_id':r['role_id'],'principal_id':'worker-'+r['role_id'],
                'reused':False,'name':r['name'],'tools':['read-source']} for r in d['proposal']['content']['roles']]}

    def prepare_result(self):
        d=self.setup();self.host();j=self.request(d);j=self.claim();d=self.propose(d)
        self.finish(j,prepared=self.prepared(d))
        return d

    def test_atomic_claim_retries_and_replay_keep_one_job(self):
        d=self.setup();self.host();j=self.request(d)
        self.assertEqual(j['id'],self.request(d)['id'])
        self.assertEqual(len(self.call('get_crew_setup_control',{'setup_id':d['id']})['jobs']),1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims=list(pool.map(lambda _:self.claim(),range(2)))
        self.assertEqual({x['id'] for x in claims},{j['id']})
        self.assertTrue(all(x['claim_count']==1 for x in claims))
        d=self.propose(d);done=self.finish(claims[0],prepared=self.prepared(d))
        self.assertEqual(done['status'],'succeeded')
        self.assertEqual(self.request({**d,'version':j['version']})['id'],j['id'])
        self.assertTrue(self.call('replay')['matched'])
        control=Service(self.root/'ledger').call(self.token,'get_crew_setup_control',{'setup_id':d['id']})
        self.assertEqual(control['prepared']['job_id'],j['id'])

    def test_exact_owner_only_and_no_bot_or_mentor_profile(self):
        from gantry.agent_connection import PROFILES
        d=self.setup();self.host();j=self.request(d)
        outsider=self.person('other-owner','human');agent=self.person('helper','agent')
        for token in (outsider,agent):
            self.fault('unauthorized',lambda:self.service.call(token,'get_crew_setup_control',{'setup_id':d['id']}))
            self.fault('unauthorized',lambda:self.service.call(token,'claim_crew_setup_job',
                {'host_id':'customer-host','instance_id':'process-one'},'foreign-claim'))
        names={'get_crew_setup_control','request_crew_setup_job','claim_crew_setup_job','finish_crew_setup_job',
               'register_crew_setup_host','heartbeat_crew_setup_host','disconnect_crew_setup_host','resume_crew_setup_job'}
        self.assertFalse(names & PROFILES['bot']);self.assertFalse(names & PROFILES['review'])
        self.assertEqual(self.claim()['id'],j['id'])

    def test_host_lease_restart_holds_and_fences_until_explicit_resume(self):
        now=[self.service.clock()];self.service.clock=lambda:now[0]
        d=self.setup();self.host();j=self.request(d);claimed=self.claim()
        self.fault('conflict',lambda:self.host(instance_id='process-two'))
        now[0]+=61000
        self.assertFalse(self.call('get_crew_setup_control',{'setup_id':d['id']})['hosts'][0]['online'])
        self.fault('runtime_unavailable',lambda:self.finish(claimed,'held'))
        self.host(instance_id='process-two')
        self.assertIsNone(self.claim('process-two'))
        held=self.call('get_crew_setup_control',{'setup_id':d['id']})['jobs'][0]
        self.assertEqual(held['status'],'held')
        self.fault('unauthorized',lambda:self.finish(claimed,'held'))
        resumed=self.call('resume_crew_setup_job',{'job_id':j['id']})
        self.assertEqual(resumed['id'],j['id'])
        claimed=self.claim('process-two');self.assertEqual(claimed['claim_count'],2)
        self.assertEqual(claimed['instance_id'],'process-two')

    def test_active_job_cannot_move_to_other_host_or_config(self):
        d=self.setup();self.host();j=self.request(d)
        self.host(host_id='second-host')
        self.fault('conflict',lambda:self.request(d,host_id='second-host'))
        self.fault('conflict',lambda:self.host(config_hash=digest('changed')))
        self.fault('stale_basis',lambda:self.request(d,config_hash=digest('changed')))
        self.fault('conflict',lambda:self.request(d,'prepare'))
        self.assertEqual(self.claim()['id'],j['id'])

    def test_claim_of_stale_setup_holds_without_provider_execution(self):
        d=self.setup();self.host();j=self.request(d);self.propose(d)
        self.assertIsNone(self.claim())
        held=self.call('get_crew_setup_control',{'setup_id':d['id']})['jobs'][0]
        self.assertEqual(held['status'],'held');self.assertEqual(held['claim_count'],0)
        self.fault('stale_basis',lambda:self.call('resume_crew_setup_job',{'job_id':j['id']}))

    def test_approval_pins_current_proposal_plan_host_and_version(self):
        d=self.prepare_result();p=self.prepared(d)
        for extra in ({'proposal_hash':digest('other')},{'runtime_plan_hash':digest('other')},
                      {'version':d['version']-1}):
            self.fault('stale_basis',lambda:self.request(d,'activate',
                **{'proposal_hash':p['proposal_hash'],'runtime_plan_hash':p['runtime_plan_hash'],**extra}))
        self.fault('invalid_input',lambda:self.request(d,'activate'))
        job=self.request(d,'activate',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash'])
        self.assertEqual(job['proposal_hash'],p['proposal_hash'])
        self.assertFalse(self.call('state').get('persistent_bots'))

    def test_finished_receipts_allow_only_reviewed_public_metadata(self):
        d=self.setup();self.host();self.request(d);j=self.claim();d=self.propose(d)
        for mutate,code in [
            (lambda p:p.update(token='private'),'invalid_input'),
            (lambda p:p['roles'][0].update(config_file='/private/config.json'),'invalid_input'),
            (lambda p:p['roles'][0].update(name='Bearer '+'x'*40),'credential_detected'),
            (lambda p:p['roles'][0].update(tools=['unapproved-tool']),'scope_denied'),
            (lambda p:p.update(proposal_hash=digest('stale')),'stale_basis')]:
            p=self.prepared(d);mutate(p);self.fault(code,lambda:self.finish(j,prepared=p))
        for summary in ['ghp_'+'x'*40,'Traceback (most recent call last): /Users/customer/private.py',
                        'Authorization: Bearer '+'x'*45]:
            self.fault('credential_detected',lambda:self.finish(j,'held',summary=summary))
        self.assertEqual(self.call('get_crew_setup_control',{'setup_id':d['id']})['jobs'][0]['status'],'running')
        self.finish(j,prepared=self.prepared(d))

    def test_prepared_receipt_invalidates_on_proposal_edit(self):
        d=self.prepare_result();proposal=copy.deepcopy(d['proposal']['content']);proposal['goal']='Clarify next saved task'
        d=self.propose(d,proposal)
        self.assertIsNone(self.call('get_crew_setup_control',{'setup_id':d['id']})['prepared'])
        self.fault('stale_basis',lambda:self.request(d,'activate',proposal_hash=d['proposal']['hash'],runtime_plan_hash=digest('runtime-plan')))

    def test_identical_proposal_rewrite_still_requires_new_preparation(self):
        d=self.prepare_result();d=self.propose(d)
        self.assertIsNone(self.call('get_crew_setup_control',{'setup_id':d['id']})['prepared'])
        self.fault('stale_basis',lambda:self.request(d,'activate',proposal_hash=d['proposal']['hash'],runtime_plan_hash=digest('runtime-plan')))

    def test_only_never_claimed_jobs_can_be_cancelled(self):
        d=self.setup();self.host();j=self.request(d);self.propose(d);self.assertIsNone(self.claim())
        cancelled=self.call('cancel_crew_setup_job',{'job_id':j['id']})
        self.assertEqual(cancelled['status'],'cancelled')
        self.host(config_hash=digest('updated'))
        d=self.call('get_crew_setup',{'setup_id':d['id']})
        next_job=self.request(d,'prepare',config_hash=digest('updated'));claimed=self.claim()
        self.finish(claimed,'held')
        self.fault('conflict',lambda:self.call('cancel_crew_setup_job',{'job_id':next_job['id']}))

    def test_new_explicit_request_after_cancel_does_not_replay_cancelled_job(self):
        d=self.setup();self.host()
        args={**self.ref(d),'host_id':'customer-host','config_hash':digest('configuration'),'action':'analyze'}
        first=self.call('request_crew_setup_job',args,'cancelled-request')
        self.call('cancel_crew_setup_job',{'job_id':first['id']})
        second=self.call('request_crew_setup_job',args)
        self.assertNotEqual(second['id'],first['id']);self.assertEqual(second['status'],'queued')
        self.assertEqual(self.call('request_crew_setup_job',args)['id'],second['id'])
        self.assertEqual(self.call('request_crew_setup_job',args,'cancelled-request')['id'],first['id'])

    def test_uncertain_job_blocks_another_setup_on_same_host(self):
        first=self.setup();self.host();self.request(first);self.finish(self.claim(),'held')
        second=self.setup()
        self.fault('conflict',lambda:self.request(second))

    def test_config_hash_cannot_describe_different_backend_or_tools(self):
        d=self.prepare_result()
        self.fault('conflict',lambda:self.host(backend='customer-command'))
        self.fault('conflict',lambda:self.host(tools=['different-tool']))
        self.host(config_hash=digest('new-config'),tools=['different-tool'])
        self.assertIsNone(self.call('get_crew_setup_control',{'setup_id':d['id']})['prepared'])

    def test_host_identifiers_cannot_persist_credentials(self):
        self.fault('credential_detected',lambda:self.host(host_id='ghp_'+'x'*40))
        self.fault('credential_detected',lambda:self.host(instance_id='ghp_'+'x'*40))

    def test_existing_human_principal_cannot_be_prepared_as_customer_worker(self):
        d=self.setup();self.host();self.request(d);j=self.claim();d=self.propose(d)
        p=self.prepared(d);p['roles'][0]['principal_id']='admin'
        self.fault('scope_denied',lambda:self.finish(j,prepared=p))

    def test_prepared_view_hides_stale_policy_until_new_setup(self):
        d=self.prepare_result();session=self.call('development_state',{'session_id':d['session_id']})['session']
        self.call('studio_execution_policy',{'session_id':session['id'],'version':session['version'],
            'enabled':True,'max_parallel':2,'max_executions':None})
        self.assertIsNone(self.call('get_crew_setup_control',{'setup_id':d['id']})['prepared'])

    def test_interrupted_analysis_after_proposal_resumes_same_job_and_preparation(self):
        d=self.setup();self.host();self.request(d);j=self.claim();d=self.propose(d)
        self.finish(j,'held');self.call('resume_crew_setup_job',{'job_id':j['id']})
        resumed=self.claim();self.assertEqual(resumed['claim_count'],2)
        self.finish(resumed,prepared=self.prepared(d))
        self.assertEqual(self.call('get_crew_setup_control',{'setup_id':d['id']})['prepared']['job_id'],j['id'])

    def test_activation_receipt_must_match_prepared_principals(self):
        d=self.prepare_result();p=self.prepared(d)
        self.request(d,'activate',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash']);j=self.claim()
        bindings=self.grants(d)
        for b in bindings:
            b['principal_id']='different-'+b['role_id'];b['request']['member_id']=b['principal_id']
        self.activate(d,bindings)
        self.fault('stale_basis',lambda:self.finish(j))
        self.assertIsNone(self.call('get_crew_setup_control',{'setup_id':d['id']})['prepared'])

    def test_direct_activation_cannot_restore_outdated_preparation(self):
        d=self.prepare_result();d=self.propose(d);d=self.activate(d)
        self.assertIsNone(self.call('get_crew_setup_control',{'setup_id':d['id']})['prepared'])

    def test_start_stop_start_is_new_lifecycle_without_duplicate_first_task(self):
        from gantry.bot_worker import BotWorker, environment_manifest
        from test_development import LocalClient
        d=self.prepare_result();p=self.prepared(d)
        self.request(d,'activate',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash']);j=self.claim()
        d=self.activate(d);self.finish(j)
        session=self.call('development_state',{'session_id':d['session_id']})['session']
        self.call('studio_execution_policy',{'session_id':session['id'],'version':session['version'],
            'enabled':True,'max_parallel':2,'max_executions':None})
        lead=d['result']['roles'][0];config={'bot_id':lead['bot_id'],'name':'Lead',
            'backend':'external_agent','workflow':'bot_development','environment_definition':'Synthetic fixture','tools':[]}
        self.call('configure_bot_runtime',{'bot_id':lead['bot_id'],'version':0,'principal_id':lead['principal_id'],
            'enabled':True,'environment':environment_manifest(config)})
        with BotWorker(LocalClient(self.service,self.bot_tokens['lead']),config,self.root/'workers',lambda *_:None):
            j=self.request(d,'start',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash']);claimed=self.claim()
            d=self.call('start_crew_setup_work',self.ref(d));self.finish(claimed)
            # Frozen time verifies lifecycle ordering does not depend on millisecond ties.
            now=self.service.clock();self.service.clock=lambda:now
            first=self.request(d,'stop');self.finish(self.claim())
            start=self.request(d,'start',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash'])
            self.finish(self.claim())
            second=self.request(d,'stop');self.finish(self.claim())
            self.assertNotEqual(first['id'],second['id'])
            self.assertEqual(self.request(d,'stop')['id'],second['id'])
            next_start=self.request(d,'start',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash'])
            self.assertNotEqual(start['id'],next_start['id'])
            self.assertEqual(len(self.call('list_bot_tasks',{'session_id':d['session_id']})['items']),1)

    def test_new_host_instance_can_start_workers_after_completed_start(self):
        from gantry.bot_worker import BotWorker, environment_manifest
        from test_development import LocalClient
        d=self.prepare_result();p=self.prepared(d)
        self.request(d,'activate',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash'])
        claimed=self.claim();d=self.activate(d);self.finish(claimed)
        session=self.call('development_state',{'session_id':d['session_id']})['session']
        self.call('studio_execution_policy',{'session_id':session['id'],'version':session['version'],
            'enabled':True,'max_parallel':2,'max_executions':None})
        lead=d['result']['roles'][0];config={'bot_id':lead['bot_id'],'name':'Lead',
            'backend':'external_agent','workflow':'bot_development','environment_definition':'Synthetic fixture','tools':[]}
        self.call('configure_bot_runtime',{'bot_id':lead['bot_id'],'version':0,'principal_id':lead['principal_id'],
            'enabled':True,'environment':environment_manifest(config)})
        with BotWorker(LocalClient(self.service,self.bot_tokens['lead']),config,self.root/'workers',lambda *_:None):
            d=self.call('start_crew_setup_work',self.ref(d))
            args={**self.ref(d),'host_id':'customer-host','config_hash':digest('configuration'),
                'action':'start','proposal_hash':p['proposal_hash'],'runtime_plan_hash':p['runtime_plan_hash'],
                'session_version':self.call('development_state',{'session_id':d['session_id']})['session']['version']}
            first=self.call('request_crew_setup_job',args,'first-start')
            self.finish(self.claim())
            self.assertEqual(self.call('request_crew_setup_job',args)['id'],first['id'])
        offline=self.call('request_crew_setup_job',args)
        self.assertNotEqual(offline['id'],first['id']);self.assertEqual(offline['status'],'queued')
        with BotWorker(LocalClient(self.service,self.bot_tokens['lead']),config,self.root/'workers',lambda *_:None):
            self.finish(self.claim())
            self.assertEqual(self.call('request_crew_setup_job',args)['id'],offline['id'])
        self.call('disconnect_crew_setup_host',{'host_id':'customer-host','instance_id':'process-one'})
        self.host(instance_id='process-two')
        second=self.call('request_crew_setup_job',args)
        self.assertNotEqual(second['id'],first['id']);self.assertEqual(second['status'],'queued')
        self.assertEqual(self.call('request_crew_setup_job',args)['id'],second['id'])
        self.assertEqual(self.call('request_crew_setup_job',args,'first-start')['id'],first['id'])
        self.assertEqual(len(self.call('list_bot_tasks',{'session_id':d['session_id']})['items']),1)

    def test_start_requires_exact_execution_session_version_at_each_boundary(self):
        d=self.prepare_result();p=self.prepared(d)
        self.request(d,'activate',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash'])
        claimed=self.claim();d=self.activate(d);self.finish(claimed)
        def policy(parallel):
            session=self.call('development_state',{'session_id':d['session_id']})['session']
            self.call('studio_execution_policy',{'session_id':session['id'],'version':session['version'],
                'enabled':True,'max_parallel':parallel,'max_executions':None})
            return self.call('development_state',{'session_id':d['session_id']})['session']['version']
        version=policy(2)
        args={**self.ref(d),'host_id':'customer-host','config_hash':digest('configuration'),'action':'start',
              'proposal_hash':p['proposal_hash'],'runtime_plan_hash':p['runtime_plan_hash']}
        self.fault('invalid_input',lambda:self.call('request_crew_setup_job',args))
        self.fault('stale_basis',lambda:self.call('request_crew_setup_job',{**args,'session_version':version-1}))
        job=self.call('request_crew_setup_job',{**args,'session_version':version})
        self.assertEqual(job['session_version'],version)
        version=policy(3);self.assertIsNone(self.claim())
        self.call('cancel_crew_setup_job',{'job_id':job['id']})
        self.call('request_crew_setup_job',{**args,'session_version':version});claimed=self.claim()
        policy(4)
        self.fault('stale_basis',lambda:self.finish(claimed))
        self.finish(claimed,'held')
        resumed=self.call('resume_crew_setup_job',{'job_id':claimed['id']})
        self.assertTrue(resumed['recovery_only']);self.assertEqual(resumed['session_version'],version)
        recovery=self.claim();self.assertEqual(recovery['id'],claimed['id'])
        self.fault('invalid_input',lambda:self.finish(recovery))
        self.assertEqual(self.finish(recovery,'cancelled')['status'],'cancelled')
        self.fault('invalid_input',lambda:self.call('request_crew_setup_job',args))
        current=self.call('development_state',{'session_id':d['session_id']})['session']['version']
        fresh=self.call('request_crew_setup_job',{**args,'session_version':current})
        self.assertNotEqual(fresh['id'],claimed['id']);self.assertFalse(fresh.get('recovery_only'))
        self.assertEqual(self.call('list_bot_tasks',{'session_id':d['session_id']})['items'],[])

    def test_stop_only_recovery_requires_offline_runtimes_and_preserves_first_task(self):
        from gantry.bot_worker import BotWorker, environment_manifest
        from test_development import LocalClient
        d=self.prepare_result();p=self.prepared(d)
        self.request(d,'activate',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash'])
        claimed=self.claim();d=self.activate(d);self.finish(claimed)
        session=self.call('development_state',{'session_id':d['session_id']})['session']
        self.call('studio_execution_policy',{'session_id':session['id'],'version':session['version'],
            'enabled':True,'max_parallel':2,'max_executions':None})
        lead=d['result']['roles'][0];config={'bot_id':lead['bot_id'],'name':'Lead',
            'backend':'external_agent','workflow':'bot_development','environment_definition':'Synthetic fixture','tools':[]}
        self.call('configure_bot_runtime',{'bot_id':lead['bot_id'],'version':0,'principal_id':lead['principal_id'],
            'enabled':True,'environment':environment_manifest(config)})
        with BotWorker(LocalClient(self.service,self.bot_tokens['lead']),config,self.root/'workers',lambda *_:None):
            d=self.call('start_crew_setup_work',self.ref(d));first=d['result']['first_task_id']
            self.request(d,'start',proposal_hash=p['proposal_hash'],runtime_plan_hash=p['runtime_plan_hash']);j=self.claim()
            self.fault('invalid_input',lambda:self.finish(j,'cancelled'))
            session=self.call('development_state',{'session_id':d['session_id']})['session']
            self.call('studio_execution_policy',{'session_id':session['id'],'version':session['version'],
                'enabled':False,'max_parallel':2,'max_executions':None})
            self.finish(j,'held');resumed=self.call('resume_crew_setup_job',{'job_id':j['id']})
            self.assertTrue(resumed['recovery_only']);recovery=self.claim()
            self.fault('runtime_unavailable',lambda:self.finish(recovery,'cancelled'))
        cancelled=self.finish(recovery,'cancelled')
        self.assertEqual(cancelled['id'],j['id']);self.assertEqual(cancelled['status'],'cancelled')
        self.assertEqual(self.call('get_crew_setup',{'setup_id':d['id']})['result']['first_task_id'],first)
        self.assertEqual(len(self.call('list_bot_tasks',{'session_id':d['session_id']})['items']),1)
