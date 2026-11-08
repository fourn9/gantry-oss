import test from 'node:test';
import assert from 'node:assert/strict';
import {createDemoAPI} from '../public/demo/demo-data.js';
import {spatialPaths,workFiles,artifactKind,evidenceFiles} from '../public/demo/studio_artifacts.js';

test('spatial links are explicit, allow multiple parts and exclude absent files',()=>{
 const state={manifest:{'a.stl':{},'b.stl':{}},state:{hierarchy:[{id:'sensor',paths:['sensor/'],spatial_paths:['a.stl','b.stl','missing.stl']}]}};
 assert.deepEqual(spatialPaths(state,'sensor/calibration.yaml'),['a.stl','b.stl']);
 assert.deepEqual(spatialPaths(state,'unknown.txt'),[]);
 assert.deepEqual(spatialPaths(state,'a.stl'),['a.stl']);
});
test('changes include additions and deletions without restricting artifact formats',()=>{
 const v={manifest:{'config.yaml':{}},diffs:[{path:'old.pdf',kind:'Deleted'},{path:'config.yaml',kind:'Added'}]};
 assert.deepEqual(workFiles(v).map(f=>f.path),['old.pdf','config.yaml']);
 assert.equal(artifactKind('robot.urdf'),'Robot model');assert.equal(artifactKind('run.csv'),'Measurements');
});
test('sample configuration and evidence are the same hash in Files and Work; missing evidence stays missing',async()=>{
 const {api}=await createDemoAPI(),d=await api('studio_work',{work_id:'bracket'}),v=d.selected;
 const f=await api('studio_library',{project_id:'bench',state_id:v.state.id,section:'files',component_id:'sensor'});
 for(const path of ['sensor/calibration.yaml','evidence/bracket-offset.csv'])assert.equal(f.items.find(f=>f.path===path)?.hash,v.manifest[path]?.hash);
 assert.ok(v.manifest['robot/arm.urdf']);assert.equal(spatialPaths(v,'sensor/calibration.yaml')[0],'cad/sensor-bracket.stl');
 const checks=evidenceFiles(v);assert.ok(checks.some(c=>c.files.some(f=>f.path==='evidence/bracket-offset.csv'&&f.available)));
 assert.ok(checks.some(c=>c.files.length===0));assert.ok(checks.every(c=>c.effective_status!=='pass'));
});
