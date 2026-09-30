// Run: node --test tests/test_review_web.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const dataModule=text=>'data:text/javascript;base64,'+Buffer.from(text).toString('base64');
const helpers=dataModule(await readFile(new URL('../gantry/web/ui.js',import.meta.url),'utf8'));
const source=(await readFile(new URL('../gantry/web/review_views.js',import.meta.url),'utf8')).replace('./ui.js',helpers);
const {reviews,review,automation}=await import(dataModule(source));
const d={session:{id:'session_1',title:'Robot'},states:{changes:[{id:'change_1',title:'CAD edit',head:'state_2',assignee:'customer'}]},contracts:[],executions:[]};
const r={id:'review_1',session_id:'session_1',change_id:'change_1',state_id:'state_2',base_state:'state_1',question:'<script>bad()</script>',stage:'concept',submitted_by:'customer',status:'pending',applicable:true,acceptance:['clearance'],specialists:{},pr_diff:[],review_responses:[],review_lessons:[]};
test('pending review is escaped and never presented as running inference',()=>{
 const html=review(r,d);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.match(html,/not an active model invocation/);assert.match(html,/does not adopt/);
});
test('review displays concrete edits, scope and unresolved evidence',()=>{
 const html=review({...r,status:'completed',applicable:false,output:{verdict:'changes_requested',scope:'head motion',rationale:'clearance fails',prediction:'contact reduced',evidence:['state_2'],unverified:['physical robot'],findings:[{id:'f1',summary:'Move bracket',paths:['part.py'],evidence:['state_2'],proposed_change:'Offset 2mm',completion_condition:'Sweep all poses'}]},specialists:{mechanical:{summary:'Collision observed',unresolved:['tolerance'],evidence:['state_2']}}},d);
 for(const text of ['Inputs changed','Offset 2mm','Sweep all poses','physical robot','Collision observed'])assert.ok(html.includes(text),text);
});
test('response and lesson history stays scoped to selected PR',()=>{
 const html=review({...r,review_responses:[{submission_id:'another',responses:[{finding_id:'secret',explanation:'unrelated'}]}],review_lessons:[{submission_id:'another',assessment:'unrelated'}]},d);assert.ok(!html.includes('unrelated'));
});
test('team ownership and pagination are explicit',()=>{
 const html=reviews(d,{items:[r],next_cursor:'review_1'},{members:[{role:'developer',principal_id:'customer',side:'user'},{role:'coordinator',principal_id:'mentor',side:'gantry'}],coordinator:'coordinator',required_roles:[]});
 for(const text of ['Customer','Gantry Mentor','Load more','not proof that an agent is online'])assert.ok(html.includes(text));
});
test('automation is an actual queue status, not a fabricated active agent',()=>{
 const html=automation({policy:{enabled:true},jobs:[{kind:'developer',principal_id:'customer',status:'failed',error:'<img src=x>'}]});assert.match(html,/Queue enabled/);assert.match(html,/connected worker is required/);assert.ok(!html.includes('<img'));assert.match(html,/failed/);
});
test('failed review exposes recovery and independent verification coverage',()=>{
 const html=review({...r,status:'failed',error:'provider_failed',recovery:{completed_roles:['mechanical'],automatic_retry:false},engineering:{checks:[{scope:'service',effective_status:'fail'}]}},d);
 for(const text of ['provider_failed','Recovery','mechanical','verification coverage','service'])assert.ok(html.includes(text),text);
});
test('inferred engineering proposal is visible without implying a pass',()=>{
 const html=review({...r,engineering_proposal:{status:'proposed',provenance:'mentor_inferred',checks:[{scope:'service',method:'Sweep extraction path'}]}},d);
 for(const text of ['Mentor-proposed roles','not confirmed roles or completed tests','Sweep extraction path'])assert.ok(html.includes(text),text);
});
