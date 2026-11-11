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
