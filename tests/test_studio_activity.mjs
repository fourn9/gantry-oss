import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {createActivityMonitor}=await import('data:text/javascript;base64,'+Buffer.from(await readFile(new URL('../gantry/web/studio_activity.js',import.meta.url),'utf8')).toString('base64'));
test('polling only notifies; never loads a new artifact and ignores unrelated ledger seq',async()=>{
 let data={works:[{id:'a',head:'1'}],seq:1},notice='';
 const monitor=createActivityMonitor({api:async()=>data,notice:x=>notice=x});
 monitor.set('studio_overview',{},data);data={...data,seq:2};await monitor.check();assert.equal(notice,'');
 data={...data,works:[{id:'a',head:'2'}]};await monitor.check();assert.match(notice,/New activity/);
});
test('poll after leaving or signing out cannot show a notice or overlap a pending request',async()=>{
 let resolve,calls=0,notice='';const monitor=createActivityMonitor({api:()=>{calls++;return new Promise(r=>resolve=r);},notice:x=>notice=x});
 monitor.set('studio_work',{work_id:'A'}, {activity_token:'1'});const checking=monitor.check();await monitor.check();assert.equal(calls,1);monitor.clear();resolve({activity_token:'2'});await checking;assert.equal(notice,'');
});
test('connection loss is visible and a successful retry clears the warning',async()=>{
 let failed=true,notice='';const monitor=createActivityMonitor({api:async()=>{if(failed)throw Error('offline');return {activity_token:'1'};},notice:x=>notice=x});
 monitor.set('studio_work',{}, {activity_token:'1'});await monitor.check();assert.match(notice,/unavailable/);failed=false;await monitor.check();assert.equal(notice,'');
});
