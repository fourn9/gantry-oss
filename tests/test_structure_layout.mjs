import test from 'node:test';
import assert from 'node:assert/strict';
import {graphLayout,graphMarkup} from '../gantry/web/studio_layout.js';
test('all recorded nodes across roots and deep branches remain accessible without overlapping cards',()=>{
 const nodes=[{id:'r',title:'Robot'},{id:'a',parent:'r',title:'Arm'},{id:'b',parent:'r',title:'Base'},{id:'other',title:'Fixture'},...Array.from({length:25},(_,i)=>({id:'p'+i,parent:i?'p'+(i-1):'a',title:'Part '+i}))];
 const g=graphLayout(nodes);assert.equal(g.nodes.length,nodes.length);assert.equal(g.edges.length,nodes.length-2);
 for(const n of g.nodes){assert.ok(n.x>=0&&n.x+184<=g.width);assert.ok(n.y>=0&&n.y+48<=g.height)}
 for(let i=0;i<g.nodes.length;i++)for(let j=i+1;j<g.nodes.length;j++){const a=g.nodes[i],b=g.nodes[j];assert.ok(a.x+184<=b.x||b.x+184<=a.x||a.y+48<=b.y||b.y+48<=a.y)}
});
test('component titles and project IDs are escaped without inline style attributes',()=>{
 const html=graphMarkup({id:'" onclick="bad',hierarchy:[{id:'r',title:'<script>'}]});
 assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(!html.includes('style='));assert.ok(html.includes('&quot;'));
});
