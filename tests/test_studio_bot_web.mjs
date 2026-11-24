import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const load=async name=>readFile(new URL('../gantry/web/'+name,import.meta.url),'utf8');
const url=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const ui=url(await load('ui.js')),key=url(await load('intent_key.js'));
const views=url((await load('studio_bot_views.js')).replace("'./ui.js'",JSON.stringify(ui)));
const {requestList,requestStatus,teamView}=await import(views);
const {createBotUI}=await import(url((await load('studio_bot_ui.js')).replace("'./ui.js'",JSON.stringify(ui)).replace("'./studio_bot_views.js'",JSON.stringify(views)).replace("'./intent_key.js'",JSON.stringify(key))));
const team={sessions:[{id:'s',title:'Assembly',mode:'execute',project:{enabled:true,lead_bot_id:'b'},bots:[{bot:{id:'b',name:'Bot',enabled:true,profile:{mission:'Inspect'},parent_bot_id:null},binding:{enabled:true,principal_id:'agent',write_scope:['a.py']},runtime:{presence:'offline'}}],principals:[{id:'agent'}],write_scope:['a.py'],requirements:['Clearance'],can_configure:true}]};
function fixture(){let modal,epoch=1;const calls=[];const context=()=>({epoch,project:{id:'p'},detail:{work:{id:'w',version:2,head:'v2',project_id:'p',session_id:'s',title:'Change',write_scope:['a.py']}},selection:{state_id:'v1',anchor:{kind:'code',path:'a.py',hash:'hash',line:3}},draft:'Explain the change'});const controller=createBotUI({api:async(...args)=>{calls.push(args);return team;},modal:(...args)=>{modal=args;},toast:()=>{},getContext:context,refresh:async()=>{}});return {controller,calls,get modal(){return modal;},setEpoch:e=>{epoch=e;}};}
test('opening Team never creates tasks or starts a runtime',async()=>{const f=fixture();await f.controller.handlers.team();assert.deepEqual(f.calls.map(x=>x[0]),['studio_team']);assert.match(f.modal[1],/offline/);});
test('Ask works without randomUUID and retries the same exact anchored request',async()=>{
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'crypto');Object.defineProperty(globalThis,'crypto',{configurable:true,value:{}});
 try{const f=fixture();await f.controller.handlers['ask-bot']();const form={bot:{value:'b'},body:{value:'Explain'}};await f.modal[2](form);await f.modal[2](form);const requests=f.calls.filter(c=>c[0]==='studio_request_bot');assert.equal(requests.length,2);assert.equal(requests[0][2],requests[1][2]);assert.equal(requests[0][1].state_id,'v1');assert.equal(requests[0][1].anchor.line,3);assert.deepEqual(requests[0][1].write_scope,[]);assert.equal(requests[0][1].mode,'ask');}
 finally{if(descriptor)Object.defineProperty(globalThis,'crypto',descriptor);else delete globalThis.crypto;}
});
test('assignment sends explicit scope and completion without changing conversation ownership',async()=>{const f=fixture();await f.controller.handlers['assign-bot']();assert.equal(f.calls.length,1);await f.modal[2]({bot:{value:'b'},body:{value:'Update'},scope:{value:'a.py'},completion:{value:'Check recorded condition\nPreserve files'}});assert.equal(f.calls[1][1].mode,'assign');assert.deepEqual(f.calls[1][1].completion,['Check recorded condition','Preserve files']);assert.equal(f.calls[1][1].version,2);});
test('late Team response cannot open a modal on another project',async()=>{let resolve,modal=false,epoch=1;const c=createBotUI({api:()=>new Promise(r=>resolve=r),modal:()=>modal=true,getContext:()=>({epoch,project:{id:'p'}})});const pending=c.handlers.team();epoch=2;resolve(team);await pending;assert.equal(modal,false);});
test('request display isolates version/selection and escapes Bot and reason',()=>{const r={id:'r',state_id:'v1',anchor:{kind:'code',path:'a.py',line:3,hash:'h'},status:'pending',mode:'ask',bot_name:'<script>',runtime:{presence:'offline'},hold_reason:'<img>'};assert.equal(requestList({bot_requests:[r]},{state_id:'v2',anchor:r.anchor}),'');const html=requestList({bot_requests:[r]},{state_id:'v1',anchor:{hash:'h',line:3,path:'a.py',kind:'code'}});assert.match(html,/runtime offline/);assert.match(html,/&lt;script&gt;/);assert.ok(!html.includes('<img>'));assert.equal(requestStatus({...r,status:'running'}),'Connection lost · recovery required');});
test('agent request leads with the request and Reply while long details stay folded',()=>{
 const anchor={kind:'work'};const html=requestList({can_comment:true,bot_requests:[{state_id:'s',anchor,bot_name:'Bot',mode:'ask',status:'pending',body:'Review clearance. '+ 'Evidence detail '.repeat(30)}]},{state_id:'s',anchor});
 assert.ok(html.indexOf('Review clearance.')<html.indexOf('Request details'));assert.match(html,/data-studio="reply"/);assert.match(html,/<details><summary>Request details/);
});
test('owner saves a one-time correction on the selected task, retaining its expected version',async()=>{
 const calls=[];let dialog;
 const view={rules:[{id:'rule',key:'routing',scope:'task',task_id:'t',version:2,enabled:true,text:'Inspect & ask',reason:'Fixture changed',author_id:'owner'}],
   tasks:[{id:'t',title:'Clamp',status:'held'}],commitments:[],selected:{id:'t',title:'Clamp',status:'held',actions:[],experience_uses:[]},can_edit:true};
 const controller=createBotUI({api:async(name,args,key)=>{calls.push({name,args,key});return name==='studio_team'?team:view;},
   modal:(...args)=>{dialog=args;},toast:()=>{},getContext:()=>({project:{id:'p'},epoch:1})});
 await controller.handlers.team();
 await controller.handlers['bot-guidance']('s|b');
 assert.match(dialog[1],/Inspect &amp; ask/);
 controller.handlers['guidance-edit']('rule');
 await dialog[2]({topic:{value:'routing'},scope:{value:'task'},targetTask:{value:'t'},advice:{value:'Check fixture'},reason:{value:'Updated drawing'},enabled:{checked:true}});
 assert.deepEqual(calls.at(-1).args,{session_id:'s',bot_id:'b',key:'routing',scope:'task',task_id:'t',version:2,text:'Check fixture',reason:'Updated drawing',enabled:true});
 assert.ok(calls.at(-1).key);
});
test('source-linked correction retains the lesson id and scoped revision',async()=>{
 const calls=[];let dialog;
 const view={rules:[{id:'r',key:'lesson-m',memory_id:'m',scope:'project',task_id:null,version:1,text:'Prior',enabled:true,author_id:'owner',reason:'Changed'}],
   tasks:[],commitments:[],can_edit:true,lessons:[{id:'m',strategy:'Choose <amber>',when_to_use:'Old fixture',when_not_to_use:['New register'],evidence:['act'],source_task_id:'task'}]};
 const controller=createBotUI({api:async(name,args)=>{calls.push(args);return name==='studio_team'?team:view;},modal:(...v)=>dialog=v,toast:()=>{},getContext:()=>({project:{id:'p'},epoch:1})});
 await controller.handlers.team();await controller.handlers['bot-guidance']('s|b');
 assert.match(dialog[1],/Choose &lt;amber&gt;/);assert.match(dialog[1],/Correct this lesson/);controller.handlers['guidance-correct']('m');
 await dialog[2]({scope:{value:'project'},advice:{value:'Read the register'},reason:{value:'Past revision'},enabled:{checked:true}});
 assert.equal(calls.at(-1).memory_id,'m');assert.equal(calls.at(-1).key,'lesson-m');assert.equal(calls.at(-1).version,1);
});
test('editing a routine preserves its next due time and omission clears it',async()=>{
 let dialog;const calls=[];
 const view={rules:[],tasks:[],commitments:[],can_delegate:true,continuation:{
   version:3,enabled:true,write_scope:[],dependencies:[],completion:['Inspect'],routine:{interval_ms:60000,first_due_at:10},next_due_at:95000}};
 const controller=createBotUI({api:async(name,args)=>{calls.push(args);return name==='studio_team'?team:view;},modal:(...v)=>dialog=v,toast:()=>{},getContext:()=>({project:{id:'p'},epoch:1})});
 await controller.handlers.team();await controller.handlers['bot-guidance']('s|b');
 const form={enabled:{checked:true},paths:{value:''},deps:{value:''},completion:{value:'Inspect'},routineMinutes:{value:'1'}};
 controller.handlers['guidance-delegate']();await dialog[2](form);
 assert.deepEqual(calls.at(-1).routine,{interval_ms:60000,first_due_at:95000});
 controller.handlers['guidance-delegate']();form.routineMinutes.value='';await dialog[2](form);
 assert.equal(calls.at(-1).routine,undefined);
});
