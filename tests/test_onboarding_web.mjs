import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const model=uri(await readFile(new URL('../gantry/web/onboarding_model.js',import.meta.url),'utf8'));
const {folderSelection,scopeSummary,encodeSelection,agentPrompt}=await import(model);
const ui=uri(await readFile(new URL('../gantry/web/ui.js',import.meta.url),'utf8'));
const views=await import(uri((await readFile(new URL('../gantry/web/onboarding_views.js',import.meta.url),'utf8')).replace("'./ui.js'",JSON.stringify(ui)).replace("'./onboarding_model.js'",JSON.stringify(model))));
const file=(path,text='source')=>({name:path.split('/').at(-1),webkitRelativePath:'project/'+path,size:Buffer.byteLength(text),arrayBuffer:async()=>Uint8Array.from(Buffer.from(text)).buffer});
test('selection preserves explicit scope; private paths never enter upload',async()=>{
 const items=folderSelection([file('.env'),file('cad/bracket.step'),file('code/control.py'),file('node_modules/lib.js')]);
 assert.equal(scopeSummary(items).excluded,2);items[2].selected=false;
 assert.deepEqual(Object.keys(await encodeSelection(items)),['cad/bracket.step']);
});
test('credential patterns and empty selection block before transmission',async()=>{
 await assert.rejects(()=>encodeSelection(folderSelection([file('code.py','ghp_'+'x'.repeat(40))])),/credential/);
 await assert.rejects(()=>encodeSelection([]),/Choose/);
});
test('source-derived strings and agent prompt are escaped and never represented as pass',()=>{
 const draft={id:'d',actors:[],version:1,snapshot:'rev_a',name:'<script>bad</script>',goal:'goal',manifest:{},status:'draft',can_confirm:true,
  discovery:{facts:[],limitations:[]},missing:[],hierarchy:[],corrections:{},stale_corrections:[],questions:[],answers:{},next_work:{title:'<img>',purpose:'Continue'}};
 const html=views.review(draft);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(html.includes('does not approve'));
 assert.match(agentPrompt(draft),/Do not execute/);assert.match(html,/Prepare with your agent/);
});
