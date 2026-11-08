import test from 'node:test';
import assert from 'node:assert/strict';
import {createDemoAPI} from '../public/demo/demo-data.js';
import {sidebar,projectHeader,projectURL} from '../public/demo/studio_views.js';
import {componentForFile,componentWork} from '../public/demo/studio_navigation.js';

test('arm sample retains requirement/check links and original pinned request',async()=>{
 const {api}=await createDemoAPI(),p=(await api('studio_overview')).projects[0];
 assert.equal(p.name,'Desktop robot arm');
 assert.ok(p.hierarchy.some(n=>n.title==='Gripper'));
 const v=await api('get_development_state',{state_id:'state_bracket_v1'});
 assert.ok(v.manifest['cad/arm-links.stl']);assert.ok(v.manifest['cad/gripper.stl']);
 const r=await api('studio_related',{project_id:p.id,state_id:v.state.id,anchor:{kind:'requirement',requirement_id:'motion-clearance',revision_id:'clearance-r1'}});
 assert.ok(r.files.every(f=>v.manifest[f.path]));assert.equal(r.requirements[0].status,'unverified');
 assert.equal((await api('studio_inbox')).items[0].anchor.line,2);
});
test('exact file chooses the leaf component, code uses its directory mapping',async()=>{
 const {api}=await createDemoAPI(),p=(await api('studio_overview')).projects[0];
 assert.equal(componentForFile(p,'cad/sensor-bracket.stl').id,'sensor');
 assert.equal(componentForFile(p,'control/motion.py').id,'control');
 assert.equal(componentForFile(p,'unmapped.txt'),undefined);
});
test('component opens its own work and does not pick work from a different component',async()=>{
 const {api}=await createDemoAPI(),d=await api('studio_overview'),p=d.projects[0];
 assert.equal(componentWork(p,d.works,'sensor').id,'bracket');
 assert.equal(componentWork(p,d.works,'control').id,'control');
 assert.equal(componentWork(p,d.works,'control','bracket').id,'bracket');
 assert.equal(componentWork(p,d.works,'frame','bracket').id,'access');
 assert.equal(componentWork(p,d.works,'gripper'),undefined);
});
test('one view selector preserves saved state and scoped discussion without a Structure tab',async()=>{
 const {api}=await createDemoAPI(),d=await api('studio_overview'),p=d.projects[0],n=p.hierarchy.find(n=>n.id==='sensor');
 assert.equal(projectURL(p.id,n.id),'studio/bench/sensor/work');
 const h=projectHeader(p,n,'files','state_bracket_v1');
 assert.ok(!h.includes('>Structure<'));assert.ok(h.includes('id="studio-view"'));assert.ok(h.includes('Requirements'));
 assert.ok(h.includes('state_bracket_v1'));assert.ok(h.includes(encodeURIComponent(JSON.stringify({kind:'component',component_id:'sensor'}))));
 const html=sidebar(d,[],{project:'bench',component:'sensor'}).projects;
 assert.match(html,/aria-current="page"[^>]*>Sensor bracket<\/a>/);
});
