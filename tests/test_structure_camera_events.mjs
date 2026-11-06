import assert from 'node:assert/strict';
import {mountStructureCamera} from '../gantry/web/studio_camera.js';
class Element extends EventTarget {
  clientWidth=800;clientHeight=600;style={};dataset={width:'1000',height:'700'};capture=new Set();
  classList={add(){},remove(){}};
  getBoundingClientRect(){return {left:20,top:30}}
  setPointerCapture(id){this.capture.add(id)} hasPointerCapture(id){return this.capture.has(id)} releasePointerCapture(id){this.capture.delete(id)}
}
let observer;
globalThis.ResizeObserver=class {constructor(fn){this.fn=fn;observer=this}observe(){}disconnect(){this.stopped=true}};
const viewport=new Element(),graph=new Element(),controls=new Element(),output={};controls.querySelector=()=>output;
let camera;const stop=mountStructureCamera(viewport,graph,controls,null,c=>camera=c);
function fire(type,props={}){const ev=new Event(type,{cancelable:true});Object.assign(ev,props);viewport.dispatchEvent(ev);return ev}
let before={...camera};
assert.equal(fire('wheel',{deltaX:30,deltaY:40,deltaMode:0,ctrlKey:false}).defaultPrevented,true);
assert.equal(camera.x,before.x-30);assert.equal(camera.y,before.y-40);
before={...camera};fire('wheel',{deltaX:0,deltaY:-20,deltaMode:0,ctrlKey:true,clientX:220,clientY:180});
assert.ok(camera.zoom>before.zoom);assert.ok(Math.abs((200-camera.x)/camera.zoom-(200-before.x)/before.zoom)<1e-8);
const pointer={isPrimary:true,pointerId:1,pointerType:'mouse',button:0,buttons:1,clientX:200,clientY:200};
fire('pointerdown',pointer);fire('pointermove',{...pointer,clientX:203});fire('pointerup',pointer);
assert.equal(fire('click',{detail:1}).defaultPrevented,false);
before={...camera};fire('pointerdown',pointer);fire('pointermove',{...pointer,clientX:260,clientY:240});fire('pointerup',pointer);
assert.equal(camera.x,before.x+60);assert.equal(camera.y,before.y+40);assert.equal(fire('click',{detail:1}).defaultPrevented,true);
assert.equal(fire('click',{detail:0}).defaultPrevented,false);
before={...camera};fire('pointerdown',pointer);fire('pointermove',{...pointer,buttons:0,clientX:280});assert.deepEqual(camera,before);assert.equal(viewport.capture.size,0);
fire('pointerdown',pointer);fire('pointerleave',pointer);fire('pointermove',{...pointer,clientX:290});assert.deepEqual(camera,before);
before={...camera};const touch={...pointer,pointerType:'touch'};fire('pointerdown',touch);fire('pointermove',{...touch,clientX:250});fire('pointerup',touch);assert.equal(camera.x,before.x+50);fire('click',{detail:1});
before={...camera};fire('gesturestart');fire('gesturechange',{scale:1.5,clientX:220,clientY:180});assert.equal(camera.zoom,before.zoom*1.5);
const gestureCamera={...camera};fire('wheel',{deltaX:0,deltaY:-20,ctrlKey:true});assert.deepEqual(camera,gestureCamera);fire('gestureend');
viewport.clientWidth=900;observer.fn();assert.equal(camera.x,gestureCamera.x+50);
stop();assert.ok(observer.stopped);before={...camera};fire('wheel',{deltaX:80,deltaY:50});assert.deepEqual(camera,before);
assert.equal(viewport.capture.size,0);
console.log('Wheel/pinch, Safari gesture deduplication, drag threshold, click suppression, resize and cleanup passed');
