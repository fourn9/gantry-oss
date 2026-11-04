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
 const html=views.review(d,[{id:'agent_1'}]);assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img src=x>'));assert.match(html,/&lt;script&gt;/);assert.match(html,/CAD owner unknown/);assert.match(html,/Reports to/);assert.match(html,/May delegate/);assert.match(html,/<details[^>]*><summary>Correct proposal JSON/);assert.match(html,/Save role/);
 assert.match(model.agentPrompt(d),/propose_crew_setup/);assert.match(model.agentPrompt(d),/untrusted/);assert.match(model.agentPrompt(d),/Do not execute/);
});
test('activation and first work controls require owner, exact proposal and actual lead readiness',()=>{
 const d=setup();assert.match(views.review(d,[]),/Connect a customer runtime/);
 d.can_confirm=false;assert.ok(!views.review(d,[{id:'agent_1'}]).includes('id="crew-activate"'));
 d.can_confirm=true;d.status='activated';d.result={organization_id:'o',lead_bot_id:'b',roles:[{role_id:'lead',bot_id:'b',principal_id:'agent_1'}]};d.readiness=[{role_id:'lead',bot_id:'b',principal_id:'agent_1',runtime:'offline',configured:true}];d.execution_enabled=true;
 assert.equal(model.canStartWork(d),false);assert.match(views.review(d,[]),/Runtime offline/);
 d.readiness[0].runtime='online';assert.equal(model.canStartWork(d),true);d.result.first_task_id='task';assert.equal(model.canStartWork(d),false);
});
function fixture(api){
 const nodes=new Map(),events={};const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',focus(){}});return nodes.get(id);};
 globalThis.document={querySelector:node,addEventListener:(type,fn)=>events[type]=fn};globalThis.location={hash:''};
 const calls=[];const controller=createCrewSetup({api:async(...args)=>{calls.push(args);return args[0]==='get_crew_setup_control'?{hosts:[],jobs:[],prepared:null}:api(...args);},toast(){},fail:error=>{throw error;}});
 const submit=form=>events.submit({target:form,submitter:{disabled:false,textContent:''},preventDefault(){}});
 return {controller,calls,node,submit};
}
test('late setup response cannot replace a screen after leaving',async()=>{
 let resolve;const f=fixture(()=>new Promise(r=>resolve=r));const pending=f.controller.render('s','setup_1');f.controller.leave();f.node('#main').innerHTML='Other project';resolve(setup());await pending;assert.equal(f.node('#main').innerHTML,'Other project');
});
test('correcting proposal sends the current frozen input basis and keeps invalid edits local',async()=>{
 const d=setup();const f=fixture(name=>name==='get_crew_setup'?d:name==='session_details'?{session:{},link:{project_id:'p'}}:name==='studio_team'?{sessions:[{id:'s',principals:[]}]}:d);await f.controller.render('s','setup_1');
 await f.submit({id:'crew-correct',proposal:{value:'{invalid'}});assert.match(f.node('#crew-error').textContent,/valid JSON/);assert.equal(f.calls.length,4);
 const corrected={...proposal,unknowns:['Owner correction']};await f.submit({id:'crew-correct',proposal:{value:JSON.stringify(corrected)}});assert.deepEqual(f.calls.find(c=>c[0]==='propose_crew_setup')[1],{setup_id:'setup_1',version:3,input_basis:'basis_1',proposal:corrected});
});
test('notes-only context uses the selected saved state and requires explicit consent',async()=>{
 const f=fixture(name=>name==='session_details'?{session:{id:'s',title:'Project',active_state:'saved'},link:{project_id:'p'}}:name==='studio_team'?{sessions:[{id:'s',principals:[]}]}:name==='list_crew_setups'?{items:[]}:{session_id:'s',id:'new'});await f.controller.render('s');
 const form={id:'crew-start',consent:{checked:false},elements:{organization_name:{value:'Workshop'}},organization_id:{value:''},notes:{value:'Owner context'}};await f.submit(form);assert.equal(f.calls.filter(c=>c[0]==='start_crew_setup').length,0);
 form.consent.checked=true;await f.submit(form);assert.deepEqual(f.calls.find(c=>c[0]==='start_crew_setup')[1],{session_id:'s',state_id:'saved',organization_name:'Workshop',notes:'Owner context',files:{},sources:[]});assert.equal(location.hash,'#studio-crew/s/new');
});

test('plain role edits preserve evidence and conventions and never silently change an existing identity',()=>{
 const original=setup().proposal.content;
 const edited=model.editRole(original,0,{name:'Integration',parent:'',mission:'Coordinate clearance',responsibilities:'Check interfaces\nReport blockers',scope:'src/',assign:true,integrate:false});
 assert.deepEqual(edited.roles[0].evidence_ids,['e1']);assert.deepEqual(edited.roles[0].profile.workflow,original.roles[0].profile.workflow);
 assert.equal(original.roles[0].name,'Lead');assert.equal(edited.roles[0].name,'Integration');
 original.roles[0].existing_bot_id='persistent';assert.throws(()=>model.editRole(original,0,{}),/existing Bot/);
});
