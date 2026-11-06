import assert from 'node:assert/strict';
import {fitCamera,zoomAt} from '../gantry/web/studio_camera.js';
const c=fitCamera(1800,700,900,600),point={x:350,y:250};
const next=zoomAt(c,c.zoom*2,point);
assert.ok(Math.abs((point.x-c.x)/c.zoom-(point.x-next.x)/next.zoom)<1e-9);
assert.ok(Math.abs((point.y-c.y)/c.zoom-(point.y-next.y)/next.zoom)<1e-9);
assert.equal(zoomAt(c,99,point).zoom,4);assert.equal(zoomAt(c,.0001,point).zoom,.1);
assert.deepEqual(zoomAt(c,c.zoom,point),c);
console.log('Cursor anchor, zoom bounds and unchanged scale passed');
