// Camera coordinates are viewport pixels; model coordinates never change.
const limit=z=>Math.max(.1,Math.min(4,z));
export function fitCamera(width,height,vw,vh){
  const zoom=limit(Math.min(1,(vw-40)/width,(vh-40)/height));
  return {zoom,x:(vw-width*zoom)/2,y:(vh-height*zoom)/2};
}
export function zoomAt(camera,scale,point){
  const zoom=limit(scale),ratio=zoom/camera.zoom;
  return {zoom,x:point.x-(point.x-camera.x)*ratio,y:point.y-(point.y-camera.y)*ratio};
}
export function mountStructureCamera(viewport,graph,controls,saved,onSave){
  const width=Number(graph.dataset.width),height=Number(graph.dataset.height);
  let camera=saved?{...saved}:fitCamera(width,height,viewport.clientWidth,viewport.clientHeight);
  let autoFit=!saved,drag=null,suppressClick=false,gesture=null,lastGesture=-Infinity;
  let vw=viewport.clientWidth,vh=viewport.clientHeight;
  const listeners=[];
  const on=(el,name,fn,options)=>{el.addEventListener(name,fn,options);listeners.push(()=>el.removeEventListener(name,fn,options));};
  const center=()=>({x:viewport.clientWidth/2,y:viewport.clientHeight/2});
  const point=ev=>{const r=viewport.getBoundingClientRect();return Number.isFinite(ev.clientX)&&Number.isFinite(ev.clientY)?{x:ev.clientX-r.left,y:ev.clientY-r.top}:center();};
  function draw(){
    graph.style.transform=`translate(${camera.x}px,${camera.y}px) scale(${camera.zoom})`;
    controls.querySelector('#graph-zoom').textContent=Math.round(camera.zoom*100)+'%';
    onSave({...camera});
  }
  function zoom(scale,anchor){autoFit=false;camera=zoomAt(camera,scale,anchor);draw();}
  function pan(x,y){autoFit=false;camera.x+=x;camera.y+=y;draw();}
  function fit(){autoFit=true;camera=fitCamera(width,height,viewport.clientWidth,viewport.clientHeight);draw();}
  on(controls,'click',ev=>{
    const b=ev.target.closest('[data-graph]');if(!b)return;
    if(b.dataset.graph==='fit')fit();else zoom(b.dataset.graph==='actual'?1:camera.zoom*(b.dataset.graph==='in'?1.25:.8),center());
  });
  on(viewport,'wheel',ev=>{
    ev.preventDefault();
    // Safari emits gesture events; ignore their accompanying wheel events.
    if(gesture||performance.now()-lastGesture<120)return;
    const unit=ev.deltaMode===1?16:ev.deltaMode===2?viewport.clientHeight:1;
    if(ev.ctrlKey)zoom(camera.zoom*Math.exp(Math.max(-1,Math.min(1,-ev.deltaY*unit*.01))),point(ev));
    else pan(-ev.deltaX*unit,-ev.deltaY*unit);
  },{passive:false});
  on(viewport,'gesturestart',ev=>{ev.preventDefault();gesture={zoom:camera.zoom};lastGesture=performance.now();},{passive:false});
  on(viewport,'gesturechange',ev=>{ev.preventDefault();if(gesture&&Number.isFinite(ev.scale)&&ev.scale>0)zoom(gesture.zoom*ev.scale,point(ev));lastGesture=performance.now();},{passive:false});
  on(viewport,'gestureend',ev=>{ev.preventDefault();gesture=null;lastGesture=performance.now();},{passive:false});
  on(viewport,'pointerdown',ev=>{
    if(!ev.isPrimary||ev.button!==0)return;
    suppressClick=false;drag={id:ev.pointerId,x:ev.clientX,y:ev.clientY,startX:ev.clientX,startY:ev.clientY,moved:false};
  });
  on(viewport,'pointermove',ev=>{
    if(!drag||drag.id!==ev.pointerId)return;
    if(ev.pointerType!=='touch'&&ev.buttons===0){end(ev);return;}
    if(!drag.moved&&Math.hypot(ev.clientX-drag.startX,ev.clientY-drag.startY)<5)return;
    ev.preventDefault();drag.moved=true;suppressClick=true;
    viewport.setPointerCapture(ev.pointerId);viewport.classList.add('is-panning');
    pan(ev.clientX-drag.x,ev.clientY-drag.y);drag.x=ev.clientX;drag.y=ev.clientY;
  });
  function end(ev){
    if(!drag||drag.id!==ev.pointerId)return;
    const id=drag.id;drag=null;viewport.classList.remove('is-panning');
    if(viewport.hasPointerCapture(id))viewport.releasePointerCapture(id);
  }
  on(viewport,'pointerleave',ev=>{if(drag&&!drag.moved)end(ev);});
  for(const name of ['pointerup','pointercancel','lostpointercapture'])on(viewport,name,end);
  on(viewport,'click',ev=>{if(suppressClick&&ev.detail!==0){suppressClick=false;ev.preventDefault();ev.stopImmediatePropagation();}},true);
  on(viewport,'dragstart',ev=>ev.preventDefault());
  on(viewport,'keydown',ev=>{
    if(ev.target!==viewport)return;
    const delta={ArrowLeft:[40,0],ArrowRight:[-40,0],ArrowUp:[0,40],ArrowDown:[0,-40]}[ev.key];
    if(delta){ev.preventDefault();pan(...delta);}else if(['+','=','-','0'].includes(ev.key)){ev.preventDefault();if(ev.key==='0')fit();else zoom(camera.zoom*(ev.key==='-'?.8:1.25),center());}
  });
  const observer=new ResizeObserver(()=>{
    const nw=viewport.clientWidth,nh=viewport.clientHeight;
    if(autoFit)camera=fitCamera(width,height,nw,nh);else{camera.x+=(nw-vw)/2;camera.y+=(nh-vh)/2;}
    vw=nw;vh=nh;draw();
  });
  observer.observe(viewport);draw();
  return ()=>{observer.disconnect();for(const remove of listeners)remove();if(drag){const id=drag.id;drag=null;if(viewport.hasPointerCapture(id))viewport.releasePointerCapture(id);}viewport.classList.remove('is-panning');};
}
