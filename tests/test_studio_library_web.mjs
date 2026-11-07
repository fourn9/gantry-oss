import test from 'node:test';
import assert from 'node:assert/strict';
import * as view from '../gantry/web/studio_library_views.js';
import {projectHeader,conversation,inbox} from '../gantry/web/studio_views.js';

test('project navigation exposes Files and Requirements without a dashboard',()=>{
 const html=projectHeader({id:'p',name:'Robot'},null,'files');
 assert.match(html,/>Files</);assert.match(html,/>Requirements</);
});
test('file tree retains paths and exact version links and escapes names',()=>{
 const html=view.fileList({project:{id:'p'},state:{id:'s'},items:[{path:'cad/<part>.step',hash:'h',size:123,storage:'bytes_saved'}],components:[]},'');
 assert.ok(html.includes('&lt;part&gt;'));assert.ok(!html.includes('<part>'));assert.ok(html.includes('cad/'));
});
test('requirement details show missing and stale evidence without claiming adoption',()=>{
 const html=view.requirementDetail({requirement_id:'r',revision_id:'old',description:'Reach <10',status:'needs_review',pinned_status:'met',current_revision:'new',gaps:['requirement_changed_or_retracted'],checks:[]});
 assert.ok(html.includes('Needs review'));assert.ok(html.includes('Reach &lt;10'));assert.ok(html.includes('old'));assert.ok(html.includes('new'));
});
test('named human and Crew participants retain stable mention IDs',()=>{
 const html=conversation({work:{head:'s'},threads:[],can_comment:true,participants:[{id:'agent_01',name:'Alex',kind:'agent',role:'Mechanical lead',team:'Robot'}]}, {state_id:'s',anchor:{kind:'requirement',requirement_id:'r',revision_id:'v'}},'',[]);
 assert.ok(html.includes('Alex'));assert.ok(html.includes('Mechanical lead'));assert.ok(html.includes('agent_01'));assert.ok(!html.includes('undefined'));
});
test('project mentions return to the exact requirement and state without fabricating work',()=>{
 const html=inbox([{id:'n',work_id:null,project_id:'p',state_id:'s',thread_id:'t',anchor:{kind:'requirement',requirement_id:'r',revision_id:'v'},title:'Robot',body:'Check',author:'a',read:false}]);
 assert.ok(html.includes('studio/p/'));assert.ok(!html.includes('studio-work/null'));assert.ok(html.includes('requirements/s/'));
});
