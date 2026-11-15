import test from 'node:test';
import assert from 'node:assert/strict';
import {checks} from '../gantry/web/studio_views.js';
const observation=(state,value,classification='declared')=>({value,unit:'mm',frame:'assembly',time_basis:'static',classification,method:'json-pointer',provenance:{view_id:'view_'+state,state_id:state,field:'offset',source:{revision_id:'artifact_'+state,path:'control.json',sha256:'a'.repeat(64),locator:'/offset'}}});
function detail(){return {work:{project_id:'project'},selected:{state:{id:'new'},engineering:{checks:[]},evaluations:[]},design_assessment:{baseline_state_id:'old',state_id:'new',engineering_evidence:{fields:[{subject:{namespace:'hierarchy',id:'carrier'},profile:'interface',name:'offset',status:'changed',before:[observation('old',2)],after:[observation('new',3)]}],impacts:[{target:{namespace:'engineering_component',id:'control'},changed_inputs:['control.json'],via:[{prerequisite:'carrier',dependent:'control'}],check_ids:['clearance']}],check_obligations:[{id:'clearance',status:'unknown',reasons:['input changed']}],unknowns:[{reason:'missing_dependency'}],conflicts:[],coverage:{partial:false}}}};}
test('Checks keeps impact collapsed and distinguishes observations from validation',()=>{
 const html=checks(detail());
 assert.match(html,/<details[^>]*><summary>Change impact &amp; evidence<\/summary>/);
 assert.match(html,/offset/);assert.match(html,/declared/);assert.match(html,/missing_dependency/);
 assert.match(html,/control\.json/);assert.match(html,/studio\/project\/carrier\/files\/old/);
 assert.match(html,/studio\/project\/carrier\/files\/new/);assert.match(html,/Not tested/);
 assert.doesNotMatch(html,/Verified/);assert.match(html,/Potential impact/);assert.match(html,/carrier → control/);
});
test('conflicts and missing provenance stay explicit and unsafe text is escaped',()=>{
 const d=detail();d.design_assessment.engineering_evidence.fields[0].after[0].value='<script>bad</script>';
 d.design_assessment.engineering_evidence.conflicts=[{name:'offset',reason:'conflicting values'}];
 d.design_assessment.engineering_evidence.coverage.partial=true;
 const html=checks(d);assert.match(html,/Partial/);assert.match(html,/conflicting values/);
 assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
});
test('unlinked project shows source identity without a broken project link',()=>{
 const d=detail();d.work.project_id=null;const html=checks(d);
 assert.match(html,/control\.json/);assert.doesNotMatch(html,/studio\/null|studio\/undefined/);
});
test('recorded plans are never execution success and keep their input state',()=>{
 const d=detail();d.verification_plans={items:[{result:{input_state:'old',question:'Does it clear?',purpose:'Nominal check',status:'planned',tool:{name:'verify'},next_steps:{pass:'Compare alternatives',fail:'Revise',unknown:'Ask owner'}}}],partial:true};
 const html=checks(d);assert.match(html,/A plan is not an execution result/);assert.match(html,/Previous \/ other version/);assert.match(html,/Partial plan history/);assert.match(html,/Ask owner/);
});

test('malformed generic plan action arrays do not break Checks',()=>{
 const d=detail();d.verification_plans={items:[{result:{input_state:'old',checks:'unexpected',missing:{length:1},assumptions:'text'}}]};
 assert.doesNotThrow(()=>checks(d));assert.match(checks(d),/Verification plans/);
});
