import test from 'node:test';
import assert from 'node:assert/strict';
import {createDemoAPI} from '../public/demo/demo-data.js';
import {componentScope,requestContext} from '../public/demo/studio_context.js';
import {checks,conversation,sidebar} from '../public/demo/studio_views.js';

test('request context restores the recorded CAD or code selection after unrelated tabs and later edits',async()=>{
 const {api}=await createDemoAPI();const request=(await api('studio_inbox')).items[0];
 await api('demo_import_update',{work_id:request.work_id,version:1});
 const d=await api('studio_work',{work_id:request.work_id,state_id:request.state_id});
 const restored={tab:'checks',file:'control/motion.py',...requestContext(d,request.thread_id)};
 assert.equal(restored.tab,'code');assert.equal(restored.compare,true);assert.equal(restored.compareState,'state_base');assert.equal(restored.conversation.anchor.line,2);assert.equal(restored.related_anchor.part,'cad/sensor-bracket.stl');assert.equal(restored.file,request.anchor.path);
 assert.equal(restored.conversation.state_id,request.state_id);assert.equal(restored.conversation.thread_id,request.thread_id);
 const anchor={kind:'code',path:'control/motion.py',line:2,hash:d.selected.manifest['control/motion.py'].hash};
 const posted=await api('studio_comment',{work_id:d.work.id,state_id:request.state_id,anchor,body:'Check this line',mentions:[]});
 const code=requestContext(await api('studio_work',{work_id:d.work.id,state_id:request.state_id}),posted.thread_id);
 assert.equal(code.tab,'code');assert.equal(code.conversation.anchor.line,2);
 assert.equal(requestContext(d,'missing'),null);
});

test('component scope is deduplicated, can narrow but cannot broaden or traverse',async()=>{
 const {api}=await createDemoAPI(),nodes=(await api('studio_overview')).projects[0].hierarchy;
 assert.deepEqual(componentScope(nodes,'sensor'),['cad/sensor-bracket.stl']);
 assert.deepEqual(componentScope(nodes,'wrist','cad/\ncad/base.stl\ncad/'),['cad/']);
 assert.deepEqual(componentScope(nodes,'control','control/motion.py'),['control/motion.py']);
 for(const p of ['cad/','control/../cad/base.stl','/control/motion.py','control/./motion.py','control\\motion.py'])assert.throws(()=>componentScope(nodes,'control',p));
 assert.throws(()=>componentScope(nodes,''));
 const w=await api('begin_change',{state_id:'state_base',title:'Bracket only',purpose:'Refine geometry',assignee:'designer',component_id:'sensor',write_scope:componentScope(nodes,'sensor')});
 const d=await api('studio_work',{work_id:w.id});assert.deepEqual(d.work.components.map(c=>c.id),['sensor']);
 await api('demo_import_update',{work_id:w.id,version:1});
 const updated=await api('studio_work',{work_id:w.id});assert.deepEqual(updated.selected.diffs.map(c=>c.path),['cad/sensor-bracket.stl']);
 await assert.rejects(api('begin_change',{state_id:'state_base',title:'Bad scope',purpose:'No',assignee:'designer',component_id:'sensor',write_scope:['control/']}));
});

test('human request names the tradeoff; visible context uses versions and a single project root',async()=>{
 const {api}=await createDemoAPI(),d=await api('studio_work',{work_id:'bracket'});
 assert.match(d.demo_request.reason,/requirement/);assert.match(d.demo_request.changed,/0.10 seconds/);
 assert.match(d.demo_request.remaining,/does not run checks/);
 assert.doesNotMatch(checks(d),/state_bracket|state_base/);
 const t=d.threads[0];assert.doesNotMatch(conversation(d,{...t},'',[]),/state_bracket/);
 const overview=await api('studio_overview');const side=sidebar(overview,[],{project:'bench'});
 assert.equal((side.projects.match(/Desktop robot arm/g)||[]).length,1);assert.match(side.projects,/Arm assembly/);
});

test('only an explicit earlier comparison is used; CAD requests select their part',async()=>{
 const {api}=await createDemoAPI(),d=await api('studio_work',{work_id:'bracket'}),t=d.threads[0];
 for(const compare_state_id of [undefined,'missing',t.state_id]){
  const context=requestContext({...d,threads:[{...t,compare_state_id}]},t.id);
  assert.equal(context.compare,false);assert.equal(context.compareState,'');
 }
 const baseline={...d,threads:[{...t,state_id:'state_base',compare_state_id:'state_bracket_v1'}]};
 assert.equal(requestContext(baseline,t.id).compare,false);
 const cad={...t,anchor:t.related_anchor};
 const context=requestContext({...d,threads:[cad]},t.id);
 assert.equal(context.tab,'cad');assert.equal(context.part,'cad/sensor-bracket.stl');assert.equal(context.compare,true);
});

test('timing evidence is the exact changed line and replies stay on that line',async()=>{
 const {api}=await createDemoAPI(),d=await api('studio_work',{work_id:'bracket'}),t=d.threads[0];
 const read=async id=>Buffer.from((await api('read_artifact_chunk',{revision_id:id,path:t.anchor.path})).content,'base64').toString().split('\n')[t.anchor.line-1];
 assert.equal(await read(t.compare_state_id),'SETTLE_TIME = 0.15');
 assert.equal(await read(t.state_id),'SETTLE_TIME = 0.25');
 const reply=await api('studio_comment',{work_id:d.work.id,state_id:t.state_id,anchor:t.anchor,body:'Keep the current timing requirement.',mentions:['design-agent']});
 assert.equal(reply.thread_id,t.id);
 const after=await api('studio_work',{work_id:d.work.id});
 assert.equal(after.threads.length,1);assert.equal(after.threads[0].anchor.line,2);
 assert.equal(after.selected.status.verification,'unverified');assert.equal(after.selected.status.adoption,'unadopted');
});
