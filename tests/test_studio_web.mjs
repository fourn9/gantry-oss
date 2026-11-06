import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const moduleFrom = text => 'data:text/javascript;base64,'+Buffer.from(text).toString('base64');
const model=await import(moduleFrom(await readFile(new URL('../gantry/web/studio_model.js',import.meta.url),'utf8')));
test('diff retains old and new line numbers for conversations',()=>{
 const d=model.lineDiff('a\nold\nz\n','a\nnew\nz\n');assert.equal(d.find(x=>x.kind==='remove').before,2);assert.equal(d.find(x=>x.kind==='add').after,2);assert.equal(model.lineDiff('x\n'.repeat(2000),'y\n'.repeat(2000)),null);
});
test('project work filtering includes nested components only in that project',()=>{assert.deepEqual(model.relatedWorks([{id:'yes',project_id:'p',components:[{id:'child'}]},{id:'no',project_id:'q',components:[{id:'child'}]}],'p','root',[{id:'root'},{id:'child',parent:'root'}]).map(x=>x.id),['yes']);});
test('checks and sharing have separate explicit labels',()=>{assert.equal(model.checkLabel('unknown'),'Unknown');assert.equal(model.versionLabel({number:2,sharing:'local'}),'v2 · Unshared checkpoint');assert.equal(model.statusText({status:'completed'}),'Completed');});
test('manifest comparison catches deleted files and stable versions',()=>{assert.deepEqual(model.fileChanges({a:{hash:'1'},b:{hash:'2'}},{a:{hash:'1'}}),[{path:'b',before:'2',after:undefined,kind:'Deleted'}]);});
const {parseMesh}=await import(moduleFrom(await readFile(new URL('../gantry/web/studio_mesh.js',import.meta.url),'utf8')));
test('STL and OBJ display actual saved geometry and reject broken coordinates',()=>{const bytes=s=>new TextEncoder().encode(s);assert.equal(parseMesh(bytes('solid fixture\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid'),'part.stl').length,1);assert.equal(parseMesh(bytes('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3'),'part.obj').length,1);assert.throws(()=>parseMesh(bytes('v NaN 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3'),'bad.obj'));});
const view=await import('../gantry/web/studio_views.js');
test('previous passing evidence never renders as a pass for this version',()=>{
 const html=view.checks({selected:{state:{id:'new'},engineering:{checks:[{id:'clearance',scope:'bracket',effective_status:'unknown',stale_inputs:['part.stl']}]},evaluations:[{scope:'motion',state_id:'old',verdict:'pass',applicable:false}]}});
 assert.ok(html.includes('Unknown'));assert.ok(html.includes('previous result does not apply'));assert.ok(html.includes('Previous version · not applicable'));assert.ok(!html.includes('Passed'));
});
test('comments and code labels escape text and retain the old-version identity',()=>{
 const html=view.conversation({work:{head:'new'},threads:[{state_id:'old',anchor:{kind:'work'},id:'t',messages:[{author:'<img>',body:'<script>alert(1)</script>',at:0,mentions:[]}]}],can_comment:false},{anchor:{kind:'work'},state_id:'old',thread_id:'t'},'',[]);
 assert.ok(html.includes('Previous version'));assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));
});
test('work scope omits ancestor components but keeps the independently changed leaves',()=>{
 assert.deepEqual(model.primaryComponents([{id:'robot',title:'Robot'},{id:'wrist',title:'Wrist',parent:'robot'},{id:'bracket',title:'Bracket',parent:'wrist'},{id:'control',title:'Control',parent:'wrist'}]).map(x=>x.id),['bracket','control']);
});
test('conversation markers never carry between versions or code lines',()=>{
 const detail={discussion_index:[{state_id:'old',anchor:{kind:'code',path:'a.py',line:2},message_count:3},{state_id:'new',anchor:{kind:'code',path:'a.py',line:5},message_count:1}]};
 assert.equal(model.commentCount(detail,'new','a.py',2),0);assert.equal(model.commentCount(detail,'old','a.py',2),3);
});
test('conversation index labels historical discussions instead of implying current relevance',()=>{
 const html=view.discussionList({selected:{state:{id:'new'}},versions:[{id:'old',number:1,sharing:'shared'}],discussion_index:[{id:'t',state_id:'old',anchor:{kind:'cad',path:'part.stl'},message_count:2}]});
 assert.ok(html.includes('Previous version'));assert.ok(html.includes('v1'));assert.ok(html.includes('2 comments'));
});
test('handoff context shows requirements and gaps without claiming physical validation',()=>{
 const html=view.workspaceContext({state:{context:{requirements:['Travel <10 mm'],constraints:['No power'],open_questions:['Clearance'],environment:{python:'3.12'}},unfinished:['Retest motion']},requirement_coverage:{configured:true,items:[{requirement_id:'req-motion',status:'unverified'}]}});
 assert.ok(html.includes('Travel &lt;10 mm'));assert.ok(html.includes('Clearance'));assert.ok(html.includes('Retest motion'));assert.ok(html.includes('unverified'));
});
