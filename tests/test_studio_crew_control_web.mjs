import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const read=name=>readFile(new URL('../gantry/web/'+name,import.meta.url),'utf8');
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const ui=uri(await read('ui.js')),key=uri(await read('intent_key.js')),modelURL=uri(await read('crew_setup_model.js'));
const viewsURL=uri((await read('crew_setup_views.js')).replace("'./ui.js'",JSON.stringify(ui)).replace("'./crew_setup_model.js'",JSON.stringify(modelURL)));
const views=await import(viewsURL);
const controllerURL=uri((await read('crew_setup.js')).replace("'./ui.js'",JSON.stringify(ui)).replace("'./intent_key.js'",JSON.stringify(key)).replace("'./crew_setup_views.js'",JSON.stringify(viewsURL)).replace("'./crew_setup_model.js'",JSON.stringify(modelURL)));
const {createCrewSetup}=await import(controllerURL);
const profile={mission:'Build with evidence',responsibilities:['Check interfaces'],workflow:[],report_when:[],focus_paths:[],onboarding:[],style:'Concise'};
const setup=()=>({id:'s1',session_id:'session',state_id:'state',version:2,status:'proposed',organization_name:'Example',can_confirm:true,manifest:{},source_limitations:[],notes:'',basis:'basis',evidence_records:[],context:{},readiness:[],proposal:{hash:'proposal-hash',content:{goal:'Continue development',organization_profile:profile,acceptance:['Record results'],unknowns:['CAD not connected'],lead_role_id:'lead',roles:[{role_id:'lead',name:'Lead',parent_role_id:null,existing_bot_id:null,profile,write_scope:['src/'],can_assign:true,can_integrate:false,rationale:'Owner notes',evidence_ids:[]}],first_task:{title:'Identify next work',completion:['Plan saved']}}}});
const control=()=>({hosts:[{id:'host',online:true,name:'Customer Mac',config_hash:'config-hash',backend:'codex-subscription',tools:[]}],jobs:[],prepared:{job_id:'prepare',host_id:'host',config_hash:'config-hash',proposal_hash:'proposal-hash',runtime_plan_hash:'runtime-hash',roles:[{role_id:'lead',principal_id:'worker',reused:false,name:'Customer runtime',tools:[]}]}});
function fixture(d=setup(),c=control(),override=()=>undefined){
 const nodes=new Map(),events={};const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'host',focus(){}});return nodes.get(id);};
 globalThis.document={querySelector:node,addEventListener:(name,fn)=>events[name]=fn,visibilityState:'visible'};
 globalThis.location={hash:''};const calls=[];
 const controller=createCrewSetup({api:async(name,args,key)=>{calls.push([name,args,key]);const result=override(name,args,key);if(result!==undefined)return result;if(name==='get_crew_setup')return d;if(name==='get_crew_setup_control')return c;if(name==='session_details')return {session:{id:'session',version:5,mode:'record'},link:{project_id:'p'}};if(name==='studio_team')return {sessions:[{id:'session',principals:[],max_parallel:2,max_executions:null}]};return {id:'job',status:'queued'};},toast(){},fail(e){throw e;}});
 const submit=form=>events.submit({target:form,submitter:{disabled:false},preventDefault(){}});
 return {controller,calls,node,submit,events};
}
test('three compact steps and host action replace mandatory terminal or JSON setup',()=>{
 const html=views.review(setup(),[],control());assert.match(html,/Sources/);assert.match(html,/Team review/);assert.match(html,/Start/);assert.match(html,/Create team/);assert.match(html,/Customer Mac/);assert.doesNotMatch(html,/Run the worker commands/);assert.match(html,/crew-role-edit/);
 const d=setup();d.proposal=null;d.status='draft';const missing=views.review(d,[],{hosts:[],jobs:[],prepared:null});assert.match(missing,/Connect a customer runtime/);assert.match(missing,/Suggest team/);assert.match(missing,/disabled/);
});
test('opening screen is read-only and approval pins both proposal and customer environment',async()=>{
 const f=fixture();await f.controller.render('session','s1');assert.ok(f.calls.every(([n])=>['get_crew_setup','session_details','studio_team','get_crew_setup_control'].includes(n)));
 await f.submit({id:'crew-create',consent:{checked:true}});
 assert.deepEqual(f.calls.find(([n])=>n==='request_crew_setup_job')[1],{setup_id:'s1',version:2,host_id:'host',config_hash:'config-hash',action:'activate',proposal_hash:'proposal-hash',runtime_plan_hash:'runtime-hash'});
 assert.ok(!f.calls.some(([n])=>n==='studio_execution_policy'));f.controller.leave();
});
test('unknown HTTP outcome reuses intent and never starts inference from refresh',async()=>{
 const d=setup();d.proposal=null;d.status='draft';const c=control();c.prepared=null;let attempts=0;
 const f=fixture(d,c,name=>{if(name==='request_crew_setup_job'&&++attempts===1)throw new Error('Connection interrupted');});await f.controller.render('session','s1');
 const form={id:'crew-suggest',consent:{checked:true},elements:{host_id:{value:'host'}}};await f.submit(form);await f.submit(form);
 const jobs=f.calls.filter(([n])=>n==='request_crew_setup_job');assert.equal(jobs.length,2);assert.equal(jobs[0][2],jobs[1][2]);assert.equal(jobs[0][1].action,'analyze');f.controller.leave();
});
test('stale/offline/preparation mismatch prevents approval',async()=>{
 for(const alter of [(d,c)=>{d.stale=true;},(d,c)=>{c.hosts[0].online=false;},(d,c)=>{c.prepared.proposal_hash='other';}]){
  const d=setup(),c=control();alter(d,c);const f=fixture(d,c);await f.controller.render('session','s1');await f.submit({id:'crew-create',consent:{checked:true}});assert.ok(!f.calls.some(([n])=>n==='request_crew_setup_job'));f.controller.leave();
 }
});
test('start requires explicit execution consent; create does not grant it',async()=>{
 const d=setup();d.status='activated';d.result={lead_bot_id:'bot',roles:[{role_id:'lead',bot_id:'bot',principal_id:'worker'}]};
 const f=fixture(d);await f.controller.render('session','s1');await f.submit({id:'crew-launch',consent:{checked:false}});assert.ok(!f.calls.some(([n])=>n==='studio_execution_policy'));
 await f.submit({id:'crew-launch',consent:{checked:true}});assert.equal(f.calls.find(([n])=>n==='studio_execution_policy')[1].enabled,true);assert.equal(f.calls.find(([n])=>n==='request_crew_setup_job')[1].action,'start');f.controller.leave();
});
test('late control read cannot overwrite different project after navigation',async()=>{
 let resolve;const f=fixture(setup(),control(),name=>name==='get_crew_setup_control'?new Promise(r=>resolve=r):undefined);
 const pending=f.controller.render('session','s1');while(!resolve)await new Promise(r=>setTimeout(r,0));f.controller.leave();f.node('#main').innerHTML='Other project';resolve(control());await pending;assert.equal(f.node('#main').innerHTML,'Other project');
});
test('visible unsaved edits block creation of the old proposal',async()=>{
 const f=fixture();await f.controller.render('session','s1');f.events.input({target:{closest:()=>({id:'edit'})}});
 await f.submit({id:'crew-create',consent:{checked:true}});assert.ok(!f.calls.some(([n])=>n==='request_crew_setup_job'));assert.match(f.node('#crew-error').textContent,/Save or cancel/);f.controller.leave();
});
test('known successful lifecycle calls retire intent; unknown responses keep it',async()=>{
 const d=setup();d.status='activated';d.execution_enabled=true;d.result={first_task_id:'existing',lead_bot_id:'bot',roles:[]};
 const f=fixture(d);await f.controller.render('session','s1');
 const form={id:'crew-launch',consent:{checked:true}};await f.submit(form);await f.submit(form);
 const jobs=f.calls.filter(([n])=>n==='request_crew_setup_job');assert.equal(jobs.length,2);assert.notEqual(jobs[0][2],jobs[1][2]);f.controller.leave();
});
test('edited execution limits are applied on Resume as well as initial Start',async()=>{
 const d=setup();d.status='activated';d.execution_enabled=true;d.result={first_task_id:'existing',roles:[]};const f=fixture(d,control(),name=>name==='studio_execution_policy'?{version:6}:undefined);
 await f.controller.render('session','s1');await f.submit({id:'crew-launch',consent:{checked:true},elements:{max_parallel:{value:'1'},max_executions:{value:'3'}}});
 const policy=f.calls.find(([n])=>n==='studio_execution_policy');assert.equal(policy[1].max_executions,3);assert.equal(policy[1].max_parallel,1);assert.ok(f.calls.findIndex(([n])=>n==='studio_execution_policy')<f.calls.findIndex(([n])=>n==='request_crew_setup_job'));assert.equal(f.calls.find(([n])=>n==='request_crew_setup_job')[1].session_version,6);f.controller.leave();
});
test('stale held Start presents stop-only recovery, not renewed execution approval',async()=>{
 const d=setup(),c=control();d.status='activated';c.jobs=[{id:'old',action:'start',status:'held',session_version:4,claim_count:1}];
 const f=fixture(d,c);await f.controller.render('session','s1');assert.match(f.node('#main').innerHTML,/Stop and reconcile/);
 await f.events.click({target:{closest:()=>({dataset:{crew:'resume',job:'old'},disabled:false})},preventDefault(){}});
 assert.deepEqual(f.calls.find(([n])=>n==='resume_crew_setup_job')[1],{job_id:'old'});
 assert.ok(!f.calls.some(([n])=>n==='studio_execution_policy'||n==='request_crew_setup_job'));f.controller.leave();
});
