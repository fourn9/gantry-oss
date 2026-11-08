"""Bot-chosen residual work uses the existing hierarchy, never auto-dispatch."""
import unittest
import test_bot_development as fixtures
from gantry.model import Fault

class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.c=fixtures.BotDevelopmentTests(); self.c.setUp(); self.addCleanup(self.c.tearDown)
    def issue(self, **extra):
        return dict(id='clearance', summary='Clearance remains unknown', disposition='verify',
            reason='Measure before selecting the candidate', evidence=[self.c.base['id']],
            requirement_refs=[], assignment_index=0, **extra)
    def test_followup_creates_real_child_and_returns_its_evidence_to_manager(self):
        task=self.c.task()
        def lead(ctx,*_):
            return {'output':self.c.answer(status='waiting',assignments=[self.c.assignment('control',kind='verify')],followups=[self.issue()])}
        with self.c.worker('lead',lead) as worker: r=worker.tick()[0]
        self.assertEqual(r.get('task',{}).get('status'),'waiting',r)
        item=r['task']['reports'][0]['report']['followups'][0]
        self.assertEqual(item['assigned_task_id'],r['task']['children'][0])
        with self.c.worker('control') as worker: worker.tick()
        v=self.c.owner.call('get_bot_task',{'task_id':task['id']})
        self.assertEqual(v['task']['status'],'pending')
        self.assertEqual(v['followups'][0]['status'],'work_completed_review_required')
        self.assertFalse(v['followups'][0]['product_complete'])
        self.assertTrue(self.c.owner.call('replay')['matched'])
    def test_false_assignment_and_foreign_consultation_rejected_atomically(self):
        task=self.c.task()
        with self.c.worker('lead') as worker:
            client=self.c.clients['lead']; claim=client.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']})
            ref={'task_id':task['id'],'fence':claim['task']['fence']}
            answer=self.c.answer(followups=[self.issue()]); answer.pop('edits')
            with self.assertRaises(Fault): client.call('finish_bot_task',{**ref,'report':answer})
            item=self.issue();item.pop('assignment_index');item.update(disposition='consult',message_id='not-this-task-consultation')
            answer=self.c.answer(followups=[item]);answer.pop('edits')
            with self.assertRaises(Fault): client.call('finish_bot_task',{**ref,'report':answer})
            view=self.c.owner.call('get_bot_task',{'task_id':task['id']})
            self.assertEqual(view['task']['children'],[]);self.assertEqual(view['task']['reports'],[])
    def test_explicit_defer_keeps_product_gap_after_task_completion(self):
        task=self.c.task('designer');item=self.issue();item.pop('assignment_index');item.update(disposition='defer',reason='Requires fixture unavailable to this worker')
        with self.c.worker('designer',lambda *_:{'output':self.c.answer(followups=[item])}) as worker:r=worker.tick()[0]
        self.assertEqual(r.get('task',{}).get('status'),'completed',r)
        view=self.c.owner.call('get_bot_task',{'task_id':task['id']})
        self.assertEqual(view['followups'][0]['status'],'deferred');self.assertFalse(view['followups'][0]['product_complete'])

    def test_grandchild_gap_remains_visible_after_manager_completes(self):
        task=self.c.task()
        with self.c.worker('lead') as worker: worker.tick()
        with self.c.worker('mechanical') as worker: worker.tick()
        item=self.issue();item.pop('assignment_index');item.update(disposition='defer')
        with self.c.worker('designer',lambda *_:{'output':self.c.answer(followups=[item])}) as worker:
            leaf=worker.tick()[0]['task']
        with self.c.worker('control') as worker: worker.tick()
        with self.c.worker('mechanical') as worker: worker.tick()
        view=self.c.owner.call('get_bot_task',{'task_id':task['id']})
        self.assertEqual(view['task']['status'],'pending')
        self.assertEqual(view['followups'][0]['source_task_id'],leaf['id'])
        self.assertEqual(view['followups'][0]['status'],'deferred')
        self.assertFalse(view['followups_truncated'])

    def test_hierarchy_result_is_bounded_and_reports_truncation(self):
        from gantry.bot_followups import view
        tasks={str(i):{'id':str(i),'children':[str(i+1)] if i<104 else [],'reports':[]} for i in range(105)}
        result=view({'bot_tasks':tasks},tasks['0'])
        self.assertTrue(result['followups_truncated'])
        self.assertEqual(result['followups'],[])
