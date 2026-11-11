import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
// Minimal DOM boundary: exercise the actual controller with deferred server replies.
// Rendering/geometry are covered separately and in the authenticated browser scenario.
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const ui=uri(`export const $=s=>document.querySelector(s);export const esc=s=>s;export const short=s=>s;export const icon=()=>'';export const download=()=>{};`);
const views=uri(`export const action=()=>'';export const hint=x=>x;export const sidebar=()=>({nav:'',projects:'',recent:''});export const projectHeader=()=>'';export const workDetail=d=>d.work.id;export const conversation=(d,s,draft)=>JSON.stringify({work:d.work.id,selection:s,draft});export const workURL=x=>'studio-work/'+x;export const projectURL=(p,n,t)=>'studio/'+p+'/'+n+'/'+t;export const workList=()=> 'work-list';`);
const model=uri(await readFile(new URL('../gantry/web/studio_model.js',import.meta.url),'utf8'));
const activity=uri(await readFile(new URL('../gantry/web/studio_activity.js',import.meta.url),'utf8'));
const mesh=uri(`export const parseMesh=()=>[];export const mountMesh=()=>({destroy(){}});`);
let code=await readFile(new URL('../gantry/web/studio.js',import.meta.url),'utf8');
for(const [name,module] of [['studio_library_views',uri('export const related=()=>"Recorded links";')],['studio_library_ui',uri('export const createLibraryUI=()=>({active:false,leave(){},reset(){},render(p,n,parts){document.querySelector("#main").innerHTML=JSON.stringify({library:true,component:n?.id,section:parts[3],state:parts[4]});}});')],['studio_layout',uri('export const createStudioLayout=()=>({leave(){},mount(){}});')],['studio_bot_ui',uri('export const createBotUI=()=>({handlers:{}});')],['ui',ui],['studio_views',views],['studio_model',model],['studio_mesh',mesh],['studio_activity',activity]])code=code.replace(`'./${name}.js'`,JSON.stringify(module));
const {createStudio}=await import(uri(code+'\n//# sourceURL=studio_controller_test.js'));
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function setup(){
 const nodes=new Map(),events={};
 const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',classList:{add(){},remove(){}},focus(){},querySelector(){return {textContent:''};}});return nodes.get(id);};
 globalThis.document={body:{classList:{add(){},remove(){}}},querySelector:node,addEventListener:(name,handler)=>events[name]=handler};
 globalThis.location={hash:'#studio-work/A'};
 const data=id=>({work:{id,head:id+'1',project_id:'p'},selected:{state:{id:id+'1'},manifest:{},diffs:[]},versions:[{id:id+'0'},{id:id+'1'}],participants:[],threads:[],capture:{missing:[]}});
 let hook;
 const calls=[];const api=async(name,args)=>{calls.push({name,args});if(hook){const x=hook(name,args);if(x!==undefined)return x;}return name==='studio_overview'?{projects:[{id:'p',hierarchy:[]}],works:[]}:data(args.work_id);};
 const studio=createStudio({api,modal(){},toast(){},fail:error=>{throw error;}});
 const click=async(name,value='',side)=>events.click({target:{closest:()=>({dataset:{studio:name,value,side}})},preventDefault(){}});
 const type=value=>events.input({target:{id:'studio-draft',value}});
 const submit=()=>events.submit({target:{id:'studio-comment-form'},submitter:{},preventDefault(){}});
 return {studio,calls,node,click,type,submit,data,hook:f=>hook=f};
}
test('sending on A then navigating and typing on B cannot erase B draft or open A',async()=>{
 const h=setup();await h.studio.render();await h.click('conversation');h.type('A comment');const wait=deferred();h.hook(name=>name==='studio_comment'?wait.promise:undefined);const sent=h.submit();
 location.hash='#studio-work/B';await h.studio.render();await h.click('conversation');h.type('B private draft');wait.resolve({thread_id:'ta'});await sent;
 await h.click('close-conversation');await h.click('conversation');const panel=JSON.parse(h.node('#studio-conversation').innerHTML);
 assert.equal(panel.work,'B');assert.equal(panel.draft,'B private draft');assert.equal(h.calls.filter(x=>x.name==='studio_work'&&x.args.work_id==='A').length,1);
});
test('a failed old artifact load cannot replace the newer work screen',async()=>{
 const h=setup();let reject;const pending=new Promise((_,r)=>reject=r);await h.studio.render();
 h.hook(name=>name==='get_development_state'?pending:undefined);await h.click('compare');
 location.hash='#studio-work/B';await h.studio.render();const before=h.node('#studio-artifact').innerHTML;reject(new Error('A failed'));await new Promise(r=>setImmediate(r));assert.equal(h.node('#studio-artifact').innerHTML,before);
});
test('late lookup of a removed code line cannot open a conversation on another work',async()=>{
 const h=setup();await h.studio.render();const wait=deferred();h.hook(name=>name==='get_development_state'?wait.promise:undefined);
 const opening=h.click('line','2','before');location.hash='#studio-work/B';await h.studio.render();await h.click('conversation');h.type('B draft');wait.resolve({manifest:{}});await opening;
 await h.click('close-conversation');await h.click('conversation');const panel=JSON.parse(h.node('#studio-conversation').innerHTML);assert.equal(panel.work,'B');assert.equal(panel.draft,'B draft');
});
test('typing more while a comment is sent preserves the new text',async()=>{
 const h=setup();await h.studio.render();await h.click('conversation');h.type('first');const wait=deferred();h.hook(name=>name==='studio_comment'?wait.promise:undefined);const sent=h.submit();h.type('next unsent comment');wait.resolve({thread_id:'ta'});await sent;assert.equal(JSON.parse(h.node('#studio-conversation').innerHTML).draft,'next unsent comment');
});
test('loading activity keeps the selected version and unsent conversation draft',async()=>{
 const h=setup();await h.studio.render();await h.click('conversation');h.type('Keep this draft');
 h.hook((name,args)=>name==='studio_work'?{...h.data('A'),work:{...h.data('A').work,head:'A2'},activity_token:'updated'}:undefined);
 await h.click('load-updates');const panel=JSON.parse(h.node('#studio-conversation').innerHTML);
 assert.equal(panel.draft,'Keep this draft');assert.equal(panel.selection.state_id,'A1');
 assert.deepEqual(h.calls.at(-1),{name:'studio_work',args:{work_id:'A',state_id:'A1'}});
});
test('an activity refresh cannot restore a discussion closed while its reply is pending',async()=>{
 const h=setup();await h.studio.render();await h.click('conversation');h.type('Keep for later');
 const wait=deferred();h.hook(name=>name==='studio_work'?wait.promise:undefined);const loading=h.click('load-updates');
 await h.click('close-conversation');h.node('#studio-conversation').innerHTML='closed';wait.resolve(h.data('A'));await loading;
 assert.equal(h.node('#studio-conversation').innerHTML,'closed');await h.click('conversation');
 assert.equal(JSON.parse(h.node('#studio-conversation').innerHTML).draft,'Keep for later');
});

const componentOverview=()=>({projects:[{id:'p',hierarchy:[{id:'sensor',title:'Sensor',paths:['sensor.stl']},{id:'empty',title:'Empty',paths:['empty.stl']}]}],works:[{id:'A',title:'Sensor work',project_id:'p',components:[{id:'sensor'}]}]});
test('component and legacy Structure links open the matching work directly',async()=>{
 const h=setup();h.hook(name=>name==='studio_overview'?componentOverview():undefined);
 for(const section of ['work','structure']){location.hash='#studio/p/sensor/'+section;await h.studio.render();assert.ok(h.node('#main').innerHTML.endsWith('A'));}
});
test('a component without work opens Files with the explicit saved state retained',async()=>{
 const h=setup();h.hook(name=>name==='studio_overview'?componentOverview():undefined);
 location.hash='#studio/p/empty/structure/saved';await h.studio.render();assert.deepEqual(JSON.parse(h.node('#main').innerHTML),{library:true,component:'empty',section:'files',state:'saved'});
});
test('multiple matching work items render one picker and honor the selected work',async()=>{
 const h=setup();const overview=componentOverview();overview.works.push({...overview.works[0],id:'B',title:'Other work'});h.hook(name=>name==='studio_overview'?overview:undefined);
 location.hash='#studio/p/sensor/work/~/B';await h.studio.render();assert.match(h.node('#main').innerHTML,/studio-work-choice/);assert.match(h.node('#main').innerHTML,/Other work/);assert.ok(h.node('#main').innerHTML.endsWith('B'));
});
test('changing to Work cannot silently replace an unrelated saved state with its head',async()=>{
 const h=setup();h.hook(name=>name==='studio_overview'?componentOverview():undefined);
 location.hash='#studio/p/sensor/work/unrelated';await h.studio.render();assert.match(h.node('#main').innerHTML,/includes the selected saved state/);
});
test('historical component Work links resolve the requested hierarchy before latest project mappings',async()=>{
 const h=setup();const historical=[{id:'removed-sensor',title:'Original sensor',paths:['sensor.stl']}];
 h.hook((name,args)=>{
  if(name==='studio_overview')return {projects:[{id:'p',hierarchy:[{id:'replacement',title:'New sensor',paths:['new.stl']}]}],works:[{id:'A',project_id:'p',components:[{id:'replacement'}]}]};
  if(name==='get_development_state')return {state:{id:'A0',hierarchy:historical}};
  if(name==='studio_related')return {works:[{id:'A',project_id:'p',components:[{id:'replacement'}]}]};
  if(name==='studio_work'){const d=h.data('A');if(args.state_id)d.selected.state={id:args.state_id,hierarchy:historical};return d;}
 });
 location.hash='#studio/p/removed-sensor/work/A0';await h.studio.render();
 assert.ok(h.node('#main').innerHTML.endsWith('A'));
 assert.ok(h.calls.some(c=>c.name==='studio_work'&&c.args.state_id==='A0'));
 assert.equal(h.calls.find(c=>c.name==='studio_related').args.anchor.component_id,'removed-sensor');
});
