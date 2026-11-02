import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const data=text=>'data:text/javascript;base64,'+Buffer.from(text).toString('base64');
const helper=data(await readFile(new URL('../gantry/web/ui.js',import.meta.url),'utf8'));
const source=(await readFile(new URL('../gantry/web/views.js',import.meta.url),'utf8')).replace('./ui.js',helper);
const {requirementCoverage}=await import(data(source));
test('unknown legacy coverage never shown as achieved',()=>{
 const html=requirementCoverage({items:[],unlinked_requirements:['<script>x</script>']});
 assert.match(html,/Coverage is unknown/);assert.ok(!html.includes('<script>'));assert.match(html,/&lt;script&gt;/);
});
test('requirement change separates historical pass from current review',()=>{
 const html=requirementCoverage({items:[{requirement_id:'motion',revision_id:'rev_old',current_revision:'rev_new',description:'Move',status:'needs_review',pinned_status:'met',checks:[],gaps:['requirement_changed_or_retracted']}],unlinked_requirements:[]});
 assert.match(html,/Needs review/);assert.match(html,/Pinned evidence/);assert.match(html,/formal adoption/);
});
