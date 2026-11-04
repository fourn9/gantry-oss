import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const read=name=>readFile(new URL('../gantry/web/'+name,import.meta.url),'utf8');
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const ui=uri(await read('ui.js')),key=uri(await read('intent_key.js'));
const modelURL=uri(await read('crew_setup_model.js'));
const model=await import(modelURL);
const viewsURL=uri((await read('crew_setup_views.js')).replace("'./ui.js'",JSON.stringify(ui)).replace("'./crew_setup_model.js'",JSON.stringify(modelURL)));
const views=await import(viewsURL);
const controllerURL=uri((await read('crew_setup.js')).replace("'./ui.js'",JSON.stringify(ui)).replace("'./intent_key.js'",JSON.stringify(key)).replace("'./crew_setup_views.js'",JSON.stringify(viewsURL)).replace("'./crew_setup_model.js'",JSON.stringify(modelURL)));
const {createCrewSetup}=await import(controllerURL);
const file=(name,text='source')=>({name,size:Buffer.byteLength(text),arrayBuffer:async()=>Uint8Array.from(Buffer.from(text)).buffer});
const profile={mission:'Deliver with evidence',responsibilities:['Inspect'],focus_paths:['src'],workflow:['Consult the lead'],report_when:['Blocked'],style:'Concise',onboarding:['Read saved state']};
const proposal={organization_profile:profile,goal:'Build safely',acceptance:['Checks recorded'],lead_role_id:'lead',roles:[{role_id:'lead',name:'Lead',parent_role_id:null,existing_bot_id:null,profile,write_scope:['src'],can_assign:true,can_integrate:false,rationale:'Owner note',evidence_ids:['e1']}],unknowns:['CAD owner unknown'],first_task:{title:'Plan next change',completion:['Plan reviewed']}};
const setup=()=>({id:'setup_1',version:3,status:'proposed',session_id:'s',state_id:'state_1',organization_name:'Workshop',notes:'Keep small',manifest:{'org.md':{hash:'h'}},evidence_records:[{id:'e1',path:'org.md',hash:'h',locator:'line 1',text:'A lead is needed',kind:'text'}],source_limitations:[],basis:'basis_1',context:{scope:['src'],existing_bots:[]},proposal:{content:structuredClone(proposal),hash:'exact_hash',author:'customer-agent'},can_confirm:true,result:null,readiness:[],execution_enabled:false});
test('export selection excludes unsafe files, preserves provider and sends only checked sources',async()=>{
 const items=model.sourceSelection([file('org.md'),file('.env'),file('people.csv'),file('macro.xlsm')]);
 assert.equal(items.filter(x=>x.excluded).length,2);items[0].provider='notion';items[2].selected=false;
 const result=await model.encodeSources(items);assert.deepEqual(Object.keys(result.files),['org.md']);assert.deepEqual(result.sources,[{path:'org.md',provider:'notion'}]);
 assert.deepEqual(await model.encodeSources([]),{files:{},sources:[]});
});
test('source bounds, duplicate paths and potential credentials fail before upload',async()=>{
 await assert.rejects(()=>model.encodeSources(model.sourceSelection(Array.from({length:31},(_,i)=>file(i+'.md')))),/30/);
 await assert.rejects(()=>model.encodeSources(model.sourceSelection([{...file('large.csv'),size:17*1024*1024}])),/16 MiB/);
 await assert.rejects(()=>model.encodeSources(model.sourceSelection([file('org.md'),file('org.md')])),/Duplicate/);
 await assert.rejects(()=>model.encodeSources(model.sourceSelection([file('org.md','ghp_'+'x'.repeat(40))])),/credential/);
});
test('human proposal review escapes source content and keeps raw JSON in optional details',()=>{
 const d=setup();d.proposal.content.roles[0].name='<script>bad</script>';d.evidence_records[0].text='<img src=x>';
 const html=views.review(d,[{id:'agent_1'}]);assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img src=x>'));assert.match(html,/&lt;script&gt;/);assert.match(html,/CAD owner unknown/);assert.match(html,/Reports to/);assert.match(html,/May delegate/);assert.match(html,/<details[^>]*><summary>Correct proposal JSON/);assert.match(html,/exact_hash/);
 assert.match(model.agentPrompt(d),/propose_crew_setup/);assert.match(model.agentPrompt(d),/untrusted/);assert.match(model.agentPrompt(d),/Do not execute/);
});
test('activation and first work controls require owner, exact proposal and actual lead readiness',()=>{
 const d=setup();assert.match(views.review(d,[]),/No eligible customer agent identities/);
 d.can_confirm=false;assert.ok(!views.review(d,[{id:'agent_1'}]).includes('id="crew-activate"'));
 d.can_confirm=true;d.status='activated';d.result={organization_id:'o',lead_bot_id:'b',roles:[{role_id:'lead',bot_id:'b',principal_id:'agent_1'}]};d.readiness=[{role_id:'lead',bot_id:'b',principal_id:'agent_1',runtime:'offline',configured:true}];d.execution_enabled=true;
 assert.equal(model.canStartWork(d),false);assert.match(views.review(d,[]),/Runtime offline/);
 d.readiness[0].runtime='online';assert.equal(model.canStartWork(d),true);d.result.first_task_id='task';assert.equal(model.canStartWork(d),false);
});
function fixture(api){
 const nodes=new Map(),events={};const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',focus(){}});return nodes.get(id);};
 globalThis.document={querySelector:node,addEventListener:(type,fn)=>events[type]=fn};globalThis.location={hash:''};
 const calls=[];const controller=createCrewSetup({api:async(...args)=>{calls.push(args);return api(...args);},toast(){},fail:error=>{throw error;}});
 const submit=form=>events.submit({target:form,submitter:{disabled:false,textContent:''},preventDefault(){}});
 return {controller,calls,node,submit};
}
test('opening saved setup only reads, and activation sends the displayed hash and exact role mapping',async()=>{
 const d=setup();const f=fixture(name=>name==='get_crew_setup'?d:name==='session_details'?{session:{project_id:'p'}}:name==='studio_team'?{sessions:[{id:'s',principals:[{id:'agent_1'}]}]}:{...d,status:'activated'});
 await f.controller.render('s','setup_1');assert.deepEqual(f.calls.map(c=>c[0]),['get_crew_setup','session_details','studio_team']);
 await f.submit({id:'crew-activate',consent:{checked:true},elements:{'principal_0':{value:'agent_1'}}});
 const call=f.calls.find(c=>c[0]==='activate_crew_setup');assert.deepEqual(call[1],{setup_id:'setup_1',version:3,proposal_hash:'exact_hash',bindings:[{role_id:'lead',principal_id:'agent_1'}]});
});
test('late setup response cannot replace a screen after leaving',async()=>{
 let resolve;const f=fixture(()=>new Promise(r=>resolve=r));const pending=f.controller.render('s','setup_1');f.controller.leave();f.node('#main').innerHTML='Other project';resolve(setup());await pending;assert.equal(f.node('#main').innerHTML,'Other project');
});
test('stale proposals cannot activate and existing agent mappings must be distinct',async()=>{
 const d=setup();d.stale=true;assert.ok(!views.review(d,[{id:'agent_1'}]).includes('id="crew-activate"'));assert.match(views.review(d,[]),/Start a fresh setup/);
 d.stale=false;d.proposal.content.roles.push({...d.proposal.content.roles[0],role_id:'child',parent_role_id:'lead'});
 const f=fixture(name=>name==='get_crew_setup'?d:name==='session_details'?{session:{project_id:'p'}}:{sessions:[{id:'s',principals:[{id:'agent_1'}]}]});await f.controller.render('s','setup_1');
 await f.submit({id:'crew-activate',consent:{checked:true},elements:{principal_0:{value:'agent_1'},principal_1:{value:'agent_1'}}});assert.equal(f.calls.filter(c=>c[0]==='activate_crew_setup').length,0);assert.match(f.node('#crew-error').textContent,/separate/);
});
test('correcting proposal sends the current frozen input basis and keeps invalid edits local',async()=>{
 const d=setup();const f=fixture(name=>name==='get_crew_setup'?d:name==='session_details'?{session:{project_id:'p'}}:name==='studio_team'?{sessions:[{id:'s',principals:[]}]}:d);await f.controller.render('s','setup_1');
 await f.submit({id:'crew-correct',proposal:{value:'{invalid'}});assert.match(f.node('#crew-error').textContent,/valid JSON/);assert.equal(f.calls.length,3);
 const corrected={...proposal,unknowns:['Owner correction']};await f.submit({id:'crew-correct',proposal:{value:JSON.stringify(corrected)}});assert.deepEqual(f.calls.find(c=>c[0]==='propose_crew_setup')[1],{setup_id:'setup_1',version:3,input_basis:'basis_1',proposal:corrected});
});
test('activation retries the same intent after an unknown response and does not enable execution',async()=>{
 const d=setup();let attempts=0;const f=fixture(name=>{if(name==='get_crew_setup')return d;if(name==='session_details')return {session:{project_id:'p'}};if(name==='studio_team')return {sessions:[{id:'s',principals:[{id:'agent_1'}]}]};if(name==='activate_crew_setup'&&++attempts===1)throw new Error('Connection interrupted');return d;});await f.controller.render('s','setup_1');
 const form={id:'crew-activate',consent:{checked:true},elements:{principal_0:{value:'agent_1'}}};await f.submit(form);await f.submit(form);
 const calls=f.calls.filter(c=>c[0]==='activate_crew_setup');assert.equal(calls.length,2);assert.equal(calls[0][2],calls[1][2]);assert.ok(!f.calls.some(c=>/start_work|execution_policy|configure_bot_runtime/.test(c[0])));
});
test('notes-only context uses the selected saved state and requires explicit consent',async()=>{
 const f=fixture(name=>name==='session_details'?{session:{id:'s',project_id:'p',title:'Project',active_state:'saved'}}:name==='studio_team'?{sessions:[{id:'s',principals:[]}]}:name==='list_crew_setups'?{items:[]}:{session_id:'s',id:'new'});await f.controller.render('s');
 const form={id:'crew-start',consent:{checked:false},elements:{organization_name:{value:'Workshop'}},organization_id:{value:''},notes:{value:'Owner context'}};await f.submit(form);assert.equal(f.calls.filter(c=>c[0]==='start_crew_setup').length,0);
 form.consent.checked=true;await f.submit(form);assert.deepEqual(f.calls.find(c=>c[0]==='start_crew_setup')[1],{session_id:'s',state_id:'saved',organization_name:'Workshop',notes:'Owner context',files:{},sources:[]});assert.equal(location.hash,'#studio-crew/s/new');
});
