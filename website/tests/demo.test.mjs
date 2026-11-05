import test from 'node:test';
import assert from 'node:assert/strict';
import {createDemoAPI} from '../public/demo/demo-data.js';

test('isolated version sharing never implies verification or adoption',async()=>{
 const {api}=await createDemoAPI();
 const before=await api('studio_work',{work_id:'bracket'});
 const next=await api('demo_import_update',{work_id:'bracket',version:before.work.version});
 const saved=await api('studio_work',{work_id:'bracket'});
 assert.equal(saved.work.sharing,'local');
 assert.equal(saved.selected.status.verification,'unverified');
 assert.equal(saved.selected.status.adoption,'unadopted');
 assert.equal(saved.selected.evaluations[0].applicable,false);
 await assert.rejects(api('studio_share_update',{work_id:'bracket',version:before.work.version,state_id:next.state.id,note:''}));
 await api('studio_share_update',{work_id:'bracket',version:saved.work.version,state_id:next.state.id,note:'Ready to discuss'});
 const shared=await api('studio_work',{work_id:'bracket'});
 assert.equal(shared.work.sharing,'shared');
 assert.equal(shared.selected.status.adoption,'unadopted');
 assert.equal(shared.selected.status.verification,'unverified');
 assert.deepEqual((await api('get_development_state',{state_id:before.selected.state.id})).manifest,before.selected.manifest);
});
test('comments and inbox remain attached to exact version and part',async()=>{
 const {api}=await createDemoAPI();const v=await api('studio_work',{work_id:'bracket'});
 const anchor={kind:'code',path:'control/motion.py',hash:v.selected.manifest['control/motion.py'].hash,line:2};
 const result=await api('studio_comment',{work_id:'bracket',state_id:v.selected.state.id,anchor,body:'@designer Inspect this',mentions:['designer']});
 const inbox=await api('studio_inbox');const item=inbox.items.find(i=>i.thread_id===result.thread_id);
 assert.equal(item.state_id,v.selected.state.id);assert.deepEqual(item.anchor,anchor);
 await api('demo_import_update',{work_id:'bracket',version:v.work.version});
 assert.ok(!(await api('studio_work',{work_id:'bracket'})).threads.some(t=>t.id===result.thread_id));
 assert.ok((await api('studio_work',{work_id:'bracket',state_id:v.selected.state.id})).threads.some(t=>t.id===result.thread_id));
 await assert.rejects(api('studio_comment',{work_id:'bracket',state_id:v.selected.state.id,anchor:{...anchor,hash:'wrong'},body:'Bad',mentions:[]}));
 await assert.rejects(api('studio_comment',{work_id:'bracket',state_id:v.selected.state.id,anchor,body:'x'.repeat(4001),mentions:[]}));
});
test('separate visitors cannot share state and reset removes edits',async()=>{
 const a=await createDemoAPI(),b=await createDemoAPI();
 const initial=await b.api('studio_work',{work_id:'bracket'});
 await a.api('demo_import_update',{work_id:'bracket',version:1});
 assert.equal((await b.api('studio_work',{work_id:'bracket'})).work.head,initial.work.head);
 await a.reset();assert.equal((await a.api('studio_work',{work_id:'bracket'})).work.head,initial.work.head);
 await assert.rejects(a.api('studio_import_update',{files:{}}));
});

test('comment text is rendered escaped, never as HTML',async()=>{
 const {conversation}=await import('../public/demo/studio_views.js');const {api}=await createDemoAPI();
 const v=await api('studio_work',{work_id:'bracket'});
 await api('studio_comment',{work_id:'bracket',state_id:v.work.head,anchor:{kind:'work'},body:'<img src=x onerror=alert(1)>',mentions:[]});
 const detail=await api('studio_work',{work_id:'bracket'});
 const html=conversation(detail,{anchor:{kind:'work'},state_id:v.work.head},'',[]);
 assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img src=x'));
});

test('new work does not merge project and work identities',async()=>{
 const {api}=await createDemoAPI();const w=await api('begin_change',{state_id:'state_base',title:'Sample task',purpose:'Inspect an input',assignee:'designer',write_scope:['control/']});
 assert.notEqual(w.id,'bench');const v=await api('studio_work',{work_id:w.id});assert.equal(v.work.project_id,'bench');assert.equal(v.work.status,'working');
});

test('agent request leads to pinned CAD and code changes; reply is not approval',async()=>{
 const {api}=await createDemoAPI();
 const inbox=await api('studio_inbox');const item=inbox.items.find(i=>i.id==='request_sample');
 assert.equal(item.author,'design-agent');assert.equal(item.reply_sent,false);
 const d=await api('studio_work',{work_id:item.work_id,state_id:item.state_id});
 assert.equal(d.work.owner.kind,'agent');assert.equal(d.demo_request.replied,false);
 assert.ok(d.selected.diffs.some(x=>x.path==='cad/sensor-bracket.stl'));
 assert.ok(d.selected.diffs.some(x=>x.path==='control/motion.py'));
 await api('studio_acknowledge',{notification_id:item.id});
 assert.equal((await api('studio_inbox')).items[0].reply_sent,false);
 await api('studio_comment',{work_id:item.work_id,state_id:item.state_id,anchor:item.anchor,body:'Please check full motion before we adopt this.',mentions:['design-agent']});
 const replied=await api('studio_work',{work_id:item.work_id,state_id:item.state_id});
 assert.equal(replied.demo_request.replied,true);
 assert.equal(replied.selected.status.verification,'unverified');
 assert.equal(replied.selected.status.adoption,'unadopted');
 assert.equal((await api('studio_inbox')).items.find(i=>i.id===item.id).reply_sent,true);
 await api('demo_import_update',{work_id:d.work.id,version:d.work.version});
 assert.equal((await api('studio_work',{work_id:d.work.id})).demo_request,null);
 assert.equal((await api('studio_work',{work_id:d.work.id,state_id:item.state_id})).demo_request.replied,true);
});

test('project collaboration links the original agent exchange and review across later edits',async()=>{
 const {api}=await createDemoAPI();
 const overview=await api('studio_overview');const c=overview.collaboration;
 const pinned=await api('studio_work',{work_id:c.work_id,state_id:c.state_id});
 assert.deepEqual(c.messages,pinned.threads.find(t=>t.id===c.thread_id).messages);
 assert.deepEqual(c.messages.map(m=>m.author),['design-agent','controls-agent','design-agent']);
 assert.equal((await api('studio_inbox')).items[0].body,c.messages.at(-1).body);
 await api('demo_import_update',{work_id:c.work_id,version:pinned.work.version});
 const after=await api('studio_overview');
 assert.equal(after.collaboration.state_id,c.state_id);
 const {projectWork}=await import('../public/demo/studio_views.js');
 const html=projectWork(after.projects[0],after.works,null,after.collaboration);
 assert.ok(html.startsWith('<div class="studio-worklist">'));
 assert.ok(html.includes('Timing requirement decision'));
 assert.ok(!html.includes('Two agents.'));
 assert.ok(html.includes('#studio-work/bracket'));
 assert.ok(!projectWork(after.projects[0],after.works,{id:'frame'},after.collaboration).includes('Two agents.'));
});
