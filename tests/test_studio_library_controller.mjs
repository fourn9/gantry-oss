import test from 'node:test';
import assert from 'node:assert/strict';
import {createLibraryUI,mergeThreads} from '../gantry/web/studio_library_ui.js';
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function setup(){
 const nodes=new Map(),events={},calls=[];let hook;
 const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',querySelector:()=>({textContent:''}),focus(){},close(){this.closed=true;}});return nodes.get(id);};
 globalThis.document={querySelector:node,addEventListener:(name,fn)=>events[name]=fn};globalThis.location={hash:''};
 const state=p=>({id:p+'-state',session_id:'session',snapshot:'snapshot',summary:'Saved',parents:[],sharing:'unshared',adoption:'unadopted',unfinished:[],capture:{missing:[]}});
 const list=p=>({state:state(p),items:[],components:[],unlinked_requirements:[]});
 const related=p=>({state:state(p),requirements:[],files:[],works:[],threads:[],bot_requests:[],participants:[],write_scope:[],session_version:1,can_comment:true});
 const api=async(name,args)=>{calls.push({name,args});const x=hook?.(name,args);if(x!==undefined)return x;return name==='studio_library'?list(args.project_id):related(args.project_id);};
 const controller=createLibraryUI({api,modal(){},toast(){},fail:e=>{throw e;},bytes:async()=>new Uint8Array(),layout:{mount(){}}});
 const render=p=>controller.render({id:p,name:p},null,['studio',p,'~','files']);
 const click=async(name,value)=>events.click({target:{closest:()=>({dataset:{library:name,value}})},preventDefault(){}});
 const type=value=>events.input({target:{id:'studio-draft',value}});
 const send=()=>events.submit({target:{id:'studio-comment-form'},submitter:{},preventDefault(){}});
 return {controller,render,click,type,send,node,list,calls,hook:fn=>hook=fn};
}
test('late state read cannot replace the newly selected project or its conversation',async()=>{
 const h=setup(),wait=deferred();h.hook((n,a)=>n==='studio_library'&&a.project_id==='A'?wait.promise:undefined);
 const old=h.render('A');await h.render('B');wait.resolve(h.list('A'));await old;
 await h.click('discussion');h.type('Question on B');h.hook(n=>n==='studio_comment'?{thread_id:'threadB'}:undefined);await h.send();
 const sent=h.calls.find(c=>c.name==='studio_comment');assert.equal(sent.args.project_id,'B');assert.equal(sent.args.state_id,'B-state');assert.equal(sent.args.work_id,undefined);
});
test('submitting then navigating cannot clear another project draft',async()=>{
 const h=setup();await h.render('A');await h.click('discussion');h.type('A message');const wait=deferred();h.hook(n=>n==='studio_comment'?wait.promise:undefined);const pending=h.send();
 await h.render('B');await h.click('discussion');h.type('B unsent');wait.resolve({thread_id:'tA'});await pending;await h.click('related');await h.click('discussion');
 assert.match(h.node('#library-panel-content').innerHTML,/B unsent/);assert.doesNotMatch(h.node('#library-panel-content').innerHTML,/A message/);
});
test('new conversation pages preserve previously read messages and deduplicate',()=>{
 const original=[{id:'t',messages:Array.from({length:60},(_,i)=>({id:String(i),body:'old'}))}];
 const latest=[{id:'t',messages:[{id:'59',body:'updated'},{id:'60',body:'new answer'}]}];
 const result=mergeThreads(original,latest)[0].messages;
 assert.equal(result.length,61);assert.equal(result.find(m=>m.id==='59').body,'updated');assert.equal(result.at(-1).body,'new answer');
});
test('selecting a saved state closes history before navigating',async()=>{
 const h=setup();await h.render('A');await h.click('select-state','old-state');
 assert.equal(h.node('#dialog').closed,true);assert.match(location.hash,/files\/old-state/);
});
