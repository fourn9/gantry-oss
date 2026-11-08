import test from 'node:test';
import assert from 'node:assert/strict';
import {createDemoAPI} from '../public/demo/demo-data.js';

test('library uses exact saved states, scopes and cursors',async()=>{
 const {api}=await createDemoAPI();
 const base=await api('studio_library',{project_id:'bench',section:'files',component_id:'control',limit:1});
 assert.equal(base.state.id,'state_base');assert.equal(base.items[0].path,'control/motion.py');
 const after=await api('studio_library',{project_id:'bench',section:'files',state_id:'state_bracket_v1',path:base.items[0].path});
 assert.notEqual(after.items[0].hash,base.items[0].hash);
 const first=await api('studio_library',{project_id:'bench',section:'files',limit:1});
 const next=await api('studio_library',{project_id:'bench',section:'files',limit:1,after:first.next});
 assert.notEqual(first.items[0].path,next.items[0].path);
 await assert.rejects(api('studio_library',{project_id:'foreign',section:'files'}));
 await assert.rejects(api('studio_library',{project_id:'bench',section:'files',component_id:'foreign'}));
});

test('requirement context retains constraints and source links without bodies',async()=>{
 const {api}=await createDemoAPI();
 const page=await api('studio_library',{project_id:'bench',state_id:'state_bracket_v1',section:'requirements'});
 const timing=page.items.find(r=>r.requirement_id==='settling-time');
 assert.equal(timing.status,'unverified');assert.ok(timing.checks[0].stale_inputs.length);
 const args={project_id:'bench',state_id:page.state.id,anchor:{kind:'requirement',requirement_id:timing.requirement_id,revision_id:timing.revision_id}};
 const related=await api('studio_related',args);
 assert.ok(related.files.some(f=>f.path==='control/motion.py'));assert.ok(related.works.every(w=>w.versions.includes(page.state.id)));
 const context=await api('studio_context',{...args,limit:1,since_state:'state_base'});
 assert.equal(context.mandatory.requirements.length,page.items.length);assert.ok(context.mandatory.constraints.length);
 assert.equal(context.delta.items.length,1);assert.ok(context.delta.next);assert.ok(!JSON.stringify(context).includes('def move_axis'));
 await assert.rejects(api('studio_related',{...args,anchor:{...args.anchor,revision_id:'wrong'}}));
});

test('all project discussion targets preserve exact Inbox anchors and reject retargeting',async()=>{
 const {api,reset}=await createDemoAPI();const v=await api('get_development_state',{state_id:'state_base'});
 const anchors=[{kind:'project'},{kind:'component',component_id:'sensor'},{kind:'file',path:'control/motion.py',hash:v.manifest['control/motion.py'].hash},{kind:'requirement',requirement_id:'settling-time',revision_id:'timing-r1'},{kind:'code',path:'control/motion.py',hash:v.manifest['control/motion.py'].hash,line:2},{kind:'cad',path:'cad/sensor-bracket.stl',hash:v.manifest['cad/sensor-bracket.stl'].hash,part:'cad/sensor-bracket.stl'}];
 for(const anchor of anchors){
  const args={project_id:'bench',state_id:'state_base',anchor};
  const result=await api('studio_comment',{...args,body:'@designer Review the saved target',mentions:['designer']});
  const related=await api('studio_related',args);assert.ok(related.threads.some(t=>t.id===result.thread_id));
  const item=(await api('studio_inbox')).items.find(i=>i.thread_id===result.thread_id);
  assert.equal(item.project_id,'bench');assert.equal(item.work_id,undefined);assert.deepEqual(item.anchor,anchor);assert.equal(item.state_id,'state_base');
  const {inbox}=await import('../public/demo/studio_views.js');const html=inbox([item]);assert.ok(html.includes('#studio/bench/'));assert.ok(!html.includes('studio-work/undefined'));
  await assert.rejects(api('studio_comment',{...args,anchor:{kind:'component',component_id:'control'},thread_id:result.thread_id,body:'Retarget',mentions:[]}));
 }
 const named=(await api('studio_related',{project_id:'bench',state_id:'state_base',anchor:{kind:'project'}})).participants;
 assert.ok(named.every(p=>p.name&&p.role));
 await assert.rejects(api('studio_comment',{project_id:'bench',state_id:'state_base',anchor:{kind:'file',path:'control/motion.py',hash:'bad'},body:'Bad',mentions:[]}));
 await reset();assert.ok(!(await api('studio_inbox')).items.some(i=>i.title==='Project conversation'));
});

test('invalid and reset state targets fail without changing conversations',async()=>{
 const {api,reset}=await createDemoAPI();
 await assert.rejects(api('studio_related',{project_id:'bench',state_id:'missing',anchor:{kind:'project'}}));
 await assert.rejects(api('studio_context',{project_id:'bench',state_id:'state_base',anchor:{kind:'project'},since_state:'missing'}));
 const imported=await api('demo_import_update',{work_id:'bracket',version:1});
 await reset();
 await assert.rejects(api('studio_library',{project_id:'bench',state_id:imported.state.id,section:'files'}));
 const before=await api('studio_inbox');
 await assert.rejects(api('studio_comment',{project_id:'bench',state_id:'state_base',anchor:{kind:'project'},body:'Bad mention',mentions:['unknown']}));
 assert.deepEqual(await api('studio_inbox'),before);
});

test('conversation paging merges messages without duplicates or target changes',async()=>{
 const {api}=await createDemoAPI();
 const args={project_id:'bench',state_id:'state_base',anchor:{kind:'component',component_id:'sensor'}};
 for(let i=0;i<3;i++)await api('studio_comment',{...args,body:'Saved message '+i,mentions:[]});
 const latest=await api('studio_related',{...args,limit:1});
 const earlier=await api('studio_related',{...args,limit:1,message_after:latest.message_next});
 assert.notEqual(latest.threads[0].messages[0].id,earlier.threads[0].messages[0].id);
 await assert.rejects(api('studio_related',{...args,message_after:'message_requirement_sample'}));
 const {mergeThreads}=await import('../public/demo/studio_library_ui.js');
 assert.equal(mergeThreads(mergeThreads(latest.threads,earlier.threads),latest.threads)[0].messages.length,2);
});

test('library rendering escapes input and keeps project/component discussion routes',async()=>{
 const {projectHeader,conversation}=await import('../public/demo/studio_views.js');
 const header=projectHeader({id:'bench',name:'Bench',structure_state:'state_base'},{id:'sensor',title:'Sensor'},'files','state_bracket_v1');
 assert.ok(header.includes('Requirements'));assert.ok(header.includes('state_bracket_v1'));assert.ok(header.includes(encodeURIComponent(JSON.stringify({kind:'component',component_id:'sensor'}))));
 const {api}=await createDemoAPI(),args={project_id:'bench',state_id:'state_base',anchor:{kind:'project'}};
 await api('studio_comment',{...args,body:'<script>bad()</script>',mentions:[]});
 const data=await api('studio_related',args);
 const html=conversation({...data,work:{head:'state_base'}},{state_id:'state_base',anchor:args.anchor},'',[]);
 assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));
});

test('published demo module graph resolves with one cache revision',async()=>{
 const {readdir,readFile,access}=await import('node:fs/promises');
 const root=new URL('../public/demo/',import.meta.url);
 for(const file of await readdir(root)){
  if(!file.endsWith('.js'))continue;
  const source=await readFile(new URL(file,root),'utf8');
  for(const match of source.matchAll(/(?:from\s*|import\s*\()(['"])(\.\/[^'"]+\.js(?:\?[^'"]*)?)\1/g)){
   const url=new URL(match[2],root);assert.equal(url.search,'?v=component-20261107',file+' import '+match[2]);url.search='';await access(url);
  }
 }
 for(const file of ['workspace.html','index.html']){
  const html=await readFile(new URL(file,root),'utf8');
  assert.match(html,/script type="module" src="\.\/(?:demo|showcase)\.js\?v=component-20261107"/);
 }
});
