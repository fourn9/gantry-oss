import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
// Minimal DOM boundary: exercise the actual controller with deferred server replies.
// Rendering/geometry are covered separately and in the authenticated browser scenario.
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const ui=uri(`export const $=s=>document.querySelector(s);export const esc=s=>s;export const short=s=>s;export const icon=()=>'';export const download=()=>{};`);
const views=uri(`export const action=()=>'';export const hint=x=>x;export const sidebar=()=>({nav:'',projects:'',recent:''});export const projectHeader=()=>'';export const workDetail=d=>d.work.id;export const conversation=(d,s,draft)=>JSON.stringify({work:d.work.id,selection:s,draft});export const workURL=x=>'studio-work/'+x;`);
const model=uri(await readFile(new URL('../gantry/web/studio_model.js',import.meta.url),'utf8'));
const mesh=uri(`export const parseMesh=()=>[];export const mountMesh=()=>({destroy(){}});`);
let code=await readFile(new URL('../gantry/web/studio.js',import.meta.url),'utf8');
for(const [name,module] of [['ui',ui],['studio_views',views],['studio_model',model],['studio_mesh',mesh]])code=code.replace(`'./${name}.js'`,JSON.stringify(module));
const {createStudio}=await import(uri(code+'\n//# sourceURL=studio_controller_test.js'));
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function setup(){
 const nodes=new Map(),events={};
 const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',classList:{add(){},remove(){}},focus(){},querySelector(){return null;}});return nodes.get(id);};
 globalThis.document={body:{classList:{add(){},remove(){}}},querySelector:node,addEventListener:(name,handler)=>events[name]=handler};
 globalThis.location={hash:'#studio-work/A'};
 const data=id=>({work:{id,head:id+'1',project_id:'p'},selected:{state:{id:id+'1'},manifest:{},diffs:[]},versions:[{id:id+'0'},{id:id+'1'}],participants:[],threads:[],capture:{missing:[]}});
 let hook;
 const calls=[];const api=async(name,args)=>{calls.push({name,args});if(hook){const x=hook(name,args);if(x!==undefined)return x;}return name==='studio_overview'?{projects:[{id:'p',hierarchy:[]}],works:[]}:data(args.work_id);};
 const studio=createStudio({api,modal(){},toast(){},fail:error=>{throw error;}});
 const click=async(name,value='',side)=>events.click({target:{closest:()=>({dataset:{studio:name,value,side}})},preventDefault(){}});
 const type=value=>events.input({target:{id:'studio-draft',value}});
 const submit=()=>events.submit({target:{id:'studio-comment-form'},submitter:{},preventDefault(){}});
 return {studio,calls,node,click,type,submit,hook:f=>hook=f};
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
