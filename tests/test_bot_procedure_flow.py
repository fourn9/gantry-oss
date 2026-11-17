"""Whole worker flow with deterministic decisions and an actual sandbox process."""
import json
import sys
import unittest

from gantry import project_sandbox
from gantry.bot_worker import environment_manifest
import test_bot_procedures as fixtures


class BotProcedureFlowTests(unittest.TestCase):
    def test_workers_request_check_select_and_reuse_procedure(self):
        fixture = fixtures.BotProcedureTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        c = fixture.c
        c.configs['designer'].update(agent_loop=True, experience_learning=True)
        c.configs['control'].update(agent_loop=True, sandbox=project_sandbox.backend(),
            tool_runtime=project_sandbox.runtime_roots(), local_tools={'check':{
                'argv':[sys.executable, '-B', '-c',
                    'from pathlib import Path; assert Path("mechanical.txt").read_text() == "1"; print("fixture passed")'],
                'timeout_seconds':20}})
        for name in ('designer', 'control'):
            c.owner.call('configure_bot_runtime', {'bot_id':name, 'version':1, 'principal_id':name,
                'enabled':True, 'environment':environment_manifest(c.configs[name])})
        mid = fixture.lesson(); task = c.task('designer', title='Clamp route')
        phase = {'name':'request', 'peer_id':None}; observed_plans = []

        def answer(action, args):
            return {'output':{'action':action, 'arguments_json':json.dumps(args),
                'rationale':'Deterministic lifecycle fixture'}, 'provider':{'kind':'fixture'}}

        def designer(context, schema, directory):
            if context.get('operation') == 'plan_from_experience':
                output = c.plan_output(context['packet'])
                if phase['name'] == 'reuse':
                    memory = next(m for m in context['packet']['recall']['items'] if m['id'] == mid)
                    self.assertEqual(memory['procedure_decision']['effective_status'], 'tested_for_scope')
                    self.assertIn('apply', memory['allowed_uses'])
                    next(d for d in output['decisions'] if d['memory_id'] == mid)['use'] = 'apply'
                observed_plans.append(output)
                return {'output':output, 'provider':{'kind':'fixture'}}
            if context.get('operation') == 'reflect_on_experience':
                return {'output':{'lessons':[], 'feedback':[], 'unknowns':['No general efficacy claim']},
                    'provider':{'kind':'fixture'}}
            step = context['round']
            self.assertLess(step, 6, context.get('last_result'))
            if phase['name'] == 'request':
                if step == 0: return answer('procedure_decision', {'memory_id':mid, 'version':0,
                    'status':'candidate', 'reason':'Test the conditional procedure before preferring it', 'check_ids':[]})
                if step == 1: return answer('ask', {'to_bot_id':'control', 'memory_id':mid,
                    'question':'Check this procedure on the saved clamp input using the approved tool', 'evidence':[]})
                return answer('finish', c.answer(status='waiting', summary='Waiting for independent scoped check'))
            if phase['name'] == 'select':
                if step == 0: return answer('inspect', {'task_id':phase['peer_id'], 'pointer':'/experience_check/result/id'})
                if step == 1: return answer('procedure_decision', {'memory_id':mid, 'version':1,
                    'status':'preferred', 'reason':'The peer recorded a passing check for these saved conditions',
                    'check_ids':[context['last_result']['value']]})
                if step == 2:
                    self.assertEqual(context['last_result'].get('status'), 'preferred', context['last_result'])
                    return answer('resolve', {'message_id':context['consultations'][0]['id'],
                        'reason':'Reviewed the returned check and its limits', 'evidence':[context['task']['state_id']]})
                return answer('finish', c.answer(summary='Selected a procedure for the checked conditions'))
            if step == 0: return answer('read', {'path':'mechanical.txt'})
            action = next(a for a in context['actions'] if a['kind'] == 'read')
            return answer('finish', c.answer(summary='Reused the scoped procedure', experience_uses=[{
                'memory_id':mid, 'action_ids':[action['id']], 'change':'Read mechanical input before routing',
                'condition_check':'Same saved basis and scoped supporting evidence'}]))

        def peer(context, schema, directory):
            self.assertLess(context['round'], 3, context.get('last_result'))
            if context['round'] == 0: return answer('tool', {'name':'check'})
            action = next(a for a in context['actions'] if a['kind'] == 'tool')
            return answer('finish', c.answer(experience_check={'verdict':'supported_for_scope',
                'reason':'Saved-input tool check passed; physical behavior remains unknown', 'action_ids':[action['id']]}))

        with c.worker('designer', designer) as worker:
            result = worker.tick()
        current = c.owner.call('get_bot_task', {'task_id':task['id']})
        self.assertEqual(current['task']['status'], 'waiting', result)
        phase['peer_id'] = current['consultations'][0]['response_task_id']
        with c.worker('control', peer) as worker:
            result = worker.tick()
        self.assertEqual(c.owner.call('get_bot_task', {'task_id':phase['peer_id']})['task']['status'], 'completed', result)
        phase['name'] = 'select'
        with c.worker('designer', designer) as worker:
            result = worker.tick()
        self.assertEqual(c.owner.call('get_bot_task', {'task_id':task['id']})['task']['status'], 'completed', result)
        phase['name'] = 'reuse'; later = c.task('designer', title='Clamp route')
        with c.worker('designer', designer) as worker:
            result = worker.tick()
        self.assertEqual(c.owner.call('get_bot_task', {'task_id':later['id']})['task']['status'], 'completed', result)
        uses = c.owner.call('get_bot_records', {'task_id':later['id'], 'kind':'learning_uses'})['items']
        self.assertEqual([v['memory_id'] for v in uses], [mid])
        decisions = c.owner.call('get_bot_records', {'task_id':task['id'], 'kind':'actions'})['items']
        self.assertEqual(sum(v['kind'] == 'procedure_decision' for v in decisions), 2)
        self.assertEqual(len(observed_plans), 3)
        self.assertTrue(c.owner.call('replay')['matched'])
