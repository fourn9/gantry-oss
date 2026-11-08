import unittest
import hashlib
import test_continuity as fixtures


class ReusableSharedChangeTests(unittest.TestCase):
    def test_reuse_still_checks_read_dependencies_on_each_target(self):
        c=fixtures.ContinuityTests(); c.setUp(); self.addCleanup(c.tearDown)
        base=c.initialize()
        change=c.call('begin_change',{'state_id':base['id'],'title':'Shared check','purpose':'Use pinned input',
                      'write_scope':['check.py'],'dependencies':['input.txt'],'assignee':'admin'})
        shared=c.share(c.checkpoint(change,{'input.txt':'initial','check.py':'print(1)'}))
        self.assertTrue(c.integrate(base,[shared])['integrated'])
        current=next(x for x in c.call('list_development_states',{'session_id':c.session['id']})['changes'] if x['id']==shared['id'])
        other=c.checkpoint(c.begin(base))['state']
        result=c.integrate(other,[current])
        self.assertFalse(result['integrated'])
        self.assertIn('dependency_changed',[x['reason'] for x in result['conflicts']])

    def test_shared_checkpoint_can_reach_two_candidates_but_not_bypass_guards(self):
        c=fixtures.ContinuityTests(); c.setUp(); self.addCleanup(c.tearDown)
        base=c.initialize()
        common=c.share(c.checkpoint(c.begin(base), {'input.txt':'shared correction'}))
        a=c.checkpoint(c.begin(base,['variant.txt']), {'input.txt':'initial','variant.txt':'A'})['state']
        b=c.checkpoint(c.begin(base,['variant.txt']), {'input.txt':'initial','variant.txt':'B'})['state']
        first=c.integrate(a,[common]); self.assertTrue(first['integrated'])
        def current_change():
            return next(x for x in c.call('list_development_states',{'session_id':c.session['id']})['changes'] if x['id']==common['id'])
        current=current_change()
        self.assertEqual(current['sharing'],'integrated')
        c.fault('stale_basis',lambda:c.integrate(b,[common]))
        second=c.integrate(b,[current]); self.assertTrue(second['integrated'])
        self.assertNotEqual(first['state']['id'],second['state']['id'])
        for state,variant in [(first['state'],'A'),(second['state'],'B')]:
            view=c.call('get_development_state',{'state_id':state['id']})
            self.assertEqual(view['status']['verification'],'unverified')
            self.assertEqual(view['status']['adoption'],'unadopted')
            self.assertEqual(state['integrated_changes'][0]['state_id'],common['head'])
            self.assertEqual(view['manifest']['variant.txt']['hash'],hashlib.sha256(variant.encode()).hexdigest())
        latest=current_change()
        self.assertFalse(c.integrate(first['state'],[latest])['integrated'])
        c.fault('invalid_state',lambda:c.checkpoint(latest,{'input.txt':'new correction'}))
        updated=c.checkpoint(c.begin(base),{'input.txt':'unshared newer correction'})
        c.fault('invalid_state',lambda:c.integrate(b,[updated['change']]))
        self.assertTrue(c.call('verify')['valid'])
        self.assertTrue(c.call('replay')['matched'])
