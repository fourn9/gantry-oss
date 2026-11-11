import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {mountMesh}=await import('data:text/javascript;base64,'+Buffer.from(await readFile(new URL('../gantry/web/studio_mesh.js',import.meta.url),'utf8')).toString('base64'));
function canvas(){
 globalThis.ResizeObserver=class{observe(){} disconnect(){}};
 globalThis.requestAnimationFrame=()=>1;globalThis.cancelAnimationFrame=()=>{};
 return {getContext:()=>({}),getBoundingClientRect:()=>({width:600,height:400}),setPointerCapture(){}};
}
const meshes=[{path:'part.stl',triangles:[[[0,0,0],[1,0,0],[0,1,0]]]}];
test('camera survives remount when conversation changes the layout',()=>{
 const first=mountMesh(canvas(),meshes,()=>{});first.view('top');first.zoom(1.5);
 const saved=first.camera();first.destroy();const second=mountMesh(canvas(),meshes,()=>{},saved);
 assert.deepEqual(second.camera(),saved);assert.equal(second.camera().zoom,1.5);assert.equal(second.camera().pitch,Math.PI/2);second.destroy();
});
test('ordinary scrolling does not zoom or trap the page; Alt scroll does',()=>{
 const c=canvas(),m=mountMesh(c,meshes,()=>{});let prevented=0;
 c.onwheel({deltaY:200,preventDefault:()=>prevented++});assert.equal(prevented,0);assert.equal(m.camera().zoom,1);
 c.onwheel({altKey:true,deltaY:200,preventDefault:()=>prevented++});assert.equal(prevented,1);assert.ok(m.camera().zoom<1);m.destroy();
});
test('orbit and zoom stay bounded and corrupt saved cameras cannot lose the model',()=>{
 const c=canvas(),m=mountMesh(c,meshes,()=>{},{yaw:Infinity,pitch:NaN,zoom:Infinity});
 assert.ok(Object.values(m.camera()).every(Number.isFinite));
 m.zoom(1e10);assert.ok(m.camera().zoom<=2);m.zoom(1e-10);assert.ok(m.camera().zoom>=.5);
 c.onpointerdown({clientX:0,clientY:0,pointerId:1});c.onpointermove({clientX:1e6,clientY:1e6});
 assert.ok(Math.abs(m.camera().pitch)<=Math.PI/2);assert.ok(Math.abs(m.camera().yaw)<=Math.PI*2);m.destroy();
});
