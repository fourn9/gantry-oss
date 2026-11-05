import test from 'node:test';
import assert from 'node:assert/strict';
import {createDemoCrew} from '../public/demo/demo-crew-model.js';

const review=()=>{const demo=createDemoCrew();demo.loadSources();demo.suggest();return demo;};
const roleValues=(role,overrides={})=>({name:role.name,parent:role.parent_role_id||'',mission:role.profile.mission,responsibilities:role.profile.responsibilities.join('\n'),scope:role.write_scope.join('\n'),assign:role.can_assign,integrate:role.can_integrate,...overrides});

test('sources are required and each visitor owns an isolated, resettable proposal',()=>{
 const a=createDemoCrew(),b=createDemoCrew();
 assert.throws(()=>a.suggest(),/sources/i);
 a.loadSources();a.suggest();
 assert.equal(b.snapshot().proposal,null);
 const snapshot=a.snapshot();snapshot.proposal.roles[0].name='Outside mutation';
 assert.notEqual(a.snapshot().proposal.roles[0].name,'Outside mutation');
 a.saveRole(0,roleValues(a.snapshot().proposal.roles[0],{name:'Edited lead'}));
 a.reset();assert.deepEqual(a.snapshot(),b.snapshot());
 a.loadSources();a.suggest();assert.notEqual(a.snapshot().proposal.roles[0].name,'Edited lead');
});

test('editing a reviewed role invalidates preparation and rejected edits are atomic',()=>{
 const demo=review();demo.prepare();const role=demo.snapshot().proposal.roles[1];
 demo.saveRole(1,roleValues(role,{name:'Bracket designer'}));
 assert.equal(demo.snapshot().preparedVersion,null);
 assert.throws(()=>demo.create(),/prepare/i);
 const before=demo.snapshot();
 assert.throws(()=>demo.saveRole(0,roleValues(before.proposal.roles[0],{parent:role.role_id})),/lead|report/i);
 assert.throws(()=>demo.saveRole(1,roleValues(role,{scope:'../private/'})),/path/i);
 assert.throws(()=>demo.saveRole(1,roleValues(role,{name:'x'.repeat(81)})),/80/);
 assert.deepEqual(demo.snapshot(),before);
});

test('Create never starts work; Start, Stop and Resume retain exactly one sample task',()=>{
 const demo=review();assert.throws(()=>demo.start(),/create/i);
 demo.prepare();demo.create();
 assert.equal(demo.snapshot().status,'ready');assert.equal(demo.snapshot().firstTask,null);
 demo.start();const task=demo.snapshot().firstTask;assert.equal(demo.snapshot().status,'running');
 demo.start();assert.deepEqual(demo.snapshot().firstTask,task);
 demo.stop();assert.equal(demo.snapshot().status,'stopped');assert.deepEqual(demo.snapshot().firstTask,task);
 demo.start();assert.equal(demo.snapshot().status,'running');assert.deepEqual(demo.snapshot().firstTask,task);
 assert.throws(()=>demo.saveRole(0,roleValues(demo.snapshot().proposal.roles[0])),/created/i);
 demo.reset();assert.equal(demo.snapshot().firstTask,null);assert.equal(demo.snapshot().status,'sources');
});

test('sample views escape role edits and disclose simulation at every step',async()=>{
 const {crewView}=await import('../public/demo/demo-crew-views.js');
 const demo=createDemoCrew();
 assert.match(crewView(demo.snapshot()),/Sample · No live agents/);
 assert.doesNotMatch(crewView(demo.snapshot()),/type="file"/);
 demo.loadSources();demo.suggest();
 const attack='<img src=x onerror=alert(1)>';
 demo.saveRole(1,roleValues(demo.snapshot().proposal.roles[1],{name:attack,mission:attack,responsibilities:attack}));
 let html=crewView(demo.snapshot());assert.match(html,/&lt;img/);assert.ok(!html.includes(attack));
 assert.match(html,/Sample · No live agents/);assert.doesNotMatch(html,/>Create team</);
 demo.prepare();html=crewView(demo.snapshot());assert.match(html,/>Create team</);assert.doesNotMatch(html,/>Start demo</);
 demo.create();html=crewView(demo.snapshot());assert.match(html,/>Start demo</);assert.match(html,/No work has started/);
 demo.start();html=crewView(demo.snapshot());assert.match(html,/Stop demo/);assert.match(html,/Simulation running/);
 demo.stop();html=crewView(demo.snapshot());assert.match(html,/Resume demo/);assert.match(html,/Sample · No live agents/);
});
