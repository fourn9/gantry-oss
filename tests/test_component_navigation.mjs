import test from 'node:test';
import assert from 'node:assert/strict';
import {componentForFile,componentWork} from '../gantry/web/studio_model.js';
import {projectHeader,sidebar} from '../gantry/web/studio_views.js';
const project={id:'p',name:'Robot',hierarchy:[{id:'root',title:'Robot',paths:['cad/']},{id:'sensor',parent:'root',title:'Sensor',paths:['cad/sensor.stl']},{id:'motion',parent:'root',title:'Motion',paths:['src/']}]};
test('file selection resolves most specific component and never a sibling prefix',()=>{
 assert.equal(componentForFile(project,'cad/sensor.stl').id,'sensor');
 assert.equal(componentForFile(project,'src/main.py').id,'motion');
 assert.equal(componentForFile(project,'src-other/main.py'),undefined);
});
test('work choice is scoped and honors only a related preferred work',()=>{
 const works=[{id:'a',project_id:'p',components:[{id:'sensor'}]},{id:'b',project_id:'p',components:[{id:'sensor'}]},{id:'foreign',project_id:'q',components:[{id:'sensor'}]}];
 assert.equal(componentWork(project,works,'sensor','b').id,'b');
 assert.equal(componentWork(project,works,'motion'),undefined);
 assert.equal(componentWork(project,works,'sensor','foreign').id,'a');
});
test('single view picker preserves saved state and omits Structure',()=>{
 const html=projectHeader(project,project.hierarchy[1],'files','saved');
 assert.match(html,/id="studio-view"/);assert.doesNotMatch(html,/>Structure</);
 assert.match(html,/studio\/p\/sensor\/work\/saved/);assert.match(html,/studio\/p\/sensor\/requirements\/saved/);
});
test('component tree declares current selection and keeps escaped labels',()=>{
 const html=sidebar({projects:[project]},[],{project:'p',component:'sensor'}).projects;
 assert.match(html,/aria-current="page"/);assert.match(html,/is-selected/);
});
const {itemPicker}=await import('../gantry/web/studio_library_views.js');
test('compact item picker keeps escaped file paths and verification gaps visible',()=>{
 const files=itemPicker({items:[{path:'cad/<sensor>.stl'}]},{kind:'file',path:'cad/<sensor>.stl'},'files');
 assert.match(files,/id="library-item"/);assert.match(files,/&lt;sensor&gt;/);assert.doesNotMatch(files,/library-browser/);
 const requirements=itemPicker({items:[{requirement_id:'r',description:'Clearance',status:'unverified'}],unlinked_requirements:['Physical test missing']},{kind:'requirement',requirement_id:'r'},'requirements');
 assert.match(requirements,/Unverified/);assert.match(requirements,/Physical test missing/);
});
