// Bounded, local mesh preview. No remote assets, native CAD execution or geometry claims.
const MAX_TRIANGLES=40000;
export function parseMesh(bytes,path){
  const triangles=[];
  const push=(a,b,c)=>{if(triangles.length>=MAX_TRIANGLES)throw new Error('Preview exceeds 40,000 triangles. Export a lighter mesh.');if(![...a,...b,...c].every(x=>Number.isFinite(x)&&Math.abs(x)<1e12))throw new Error('Invalid mesh coordinates.');triangles.push([a,b,c]);};
  if(/\.stl$/i.test(path)){
    const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
    const count=bytes.length>=84?view.getUint32(80,true):0;
    if(bytes.length>=84&&84+50*count===bytes.length){
      if(count>MAX_TRIANGLES)throw new Error('Preview exceeds 40,000 triangles. Export a lighter mesh.');
      for(let i=0;i<count;i++){const start=84+i*50+12;push(...[0,1,2].map(v=>[0,1,2].map(k=>view.getFloat32(start+v*12+k*4,true))));}
    }else{
      const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes),vertex=/\bvertex\s+(\S+)\s+(\S+)\s+(\S+)/g;let m,verts=[];
      if(!/^\s*solid\b/i.test(text))throw new Error('Unsupported or damaged STL.');
      while((m=vertex.exec(text))){verts.push(m.slice(1).map(Number));if(verts.length===3){push(...verts);verts=[];}}
      if(verts.length)throw new Error('Incomplete STL triangle.');
    }
  }else if(/\.obj$/i.test(path)){
    const vertices=[];for(const line of new TextDecoder('utf-8',{fatal:true}).decode(bytes).split(/\r?\n/)){
      const [kind,...fields]=line.trim().split(/\s+/);
      if(kind==='v'){if(vertices.length>MAX_TRIANGLES*3)throw new Error('Mesh is too large.');vertices.push(fields.slice(0,3).map(Number));}
      if(kind==='f'){
        if(fields.length<3||fields.length>64)throw new Error('Unsupported OBJ face.');
        const face=fields.map(f=>{const i=Number(f.split('/')[0]);const v=vertices[i<0?vertices.length+i:i-1];if(!Number.isInteger(i)||!v||v.length!==3)throw new Error('Invalid OBJ vertex.');return v;});
        for(let i=1;i<face.length-1;i++)push(face[0],face[i],face[i+1]);
      }
    }
  }else throw new Error('This format needs a saved STL or OBJ preview.');
  if(!triangles.length)throw new Error('No triangles in this preview.');return triangles;
}
export function mountMesh(canvas,meshes,onSelect,initial='iso',comments={}){
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Canvas preview is unavailable.');
  let yaw=-.65,pitch=.75,zoom=1,pressed=null,frame=0,selected='',faces=[],closed=false;
  let min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
  for(const mesh of meshes)for(const tri of mesh.triangles)for(const v of tri)for(let i=0;i<3;i++){min[i]=Math.min(min[i],v[i]);max[i]=Math.max(max[i],v[i]);}
  const markers=meshes.filter(m=>!m.previous&&comments[m.path]).map(m=>{const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];for(const t of m.triangles)for(const v of t)for(let i=0;i<3;i++){lo[i]=Math.min(lo[i],v[i]);hi[i]=Math.max(hi[i],v[i]);}return {path:m.path,at:lo.map((v,i)=>(v+hi[i])/2)};});
  const center=min.map((n,i)=>(n+max[i])/2),span=Math.max(...min.map((n,i)=>max[i]-n),1e-6);
  function point(v){let [x,y,z]=v.map((n,i)=>(n-center[i])/span);const X=x*Math.cos(yaw)-y*Math.sin(yaw),Y=x*Math.sin(yaw)+y*Math.cos(yaw);return [X,Y*Math.sin(pitch)-z*Math.cos(pitch),Y*Math.cos(pitch)+z*Math.sin(pitch)];}
  function draw(){
    if(closed)return;const rect=canvas.getBoundingClientRect(),w=rect.width,h=rect.height,dpr=Math.min(devicePixelRatio||1,2);canvas.width=w*dpr;canvas.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
    const scale=Math.min(w,h)*.9*zoom;faces=[];
    for(const mesh of meshes)for(const tri of mesh.triangles){
      const p=tri.map(point),a=p[1].map((v,i)=>v-p[0][i]),b=p[2].map((v,i)=>v-p[0][i]);
      const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],len=Math.hypot(...n)||1;
      // A fixed soft light describes solid faces without exposing STL diagonals.
      const shade=.76+.24*Math.abs((n[0]*-.35+n[1]*-.6+n[2]*.72)/len);
      faces.push({p:p.map(v=>[w/2+v[0]*scale,h/2+v[1]*scale]),z:p.reduce((n,v)=>n+v[2],0)/3,mesh,shade});
    }
    faces.sort((a,b)=>a.z-b.z);
    for(const f of faces){
      ctx.beginPath();f.p.forEach((v,i)=>i?ctx.lineTo(...v):ctx.moveTo(...v));ctx.closePath();
      const old=f.mesh.previous,chosen=f.mesh.path===selected,base=chosen?[119,173,151]:[218,224,228];
      ctx.fillStyle=old?'rgba(172,129,87,.12)':`rgb(${base.map(v=>Math.round(v*f.shade)).join(',')})`;
      ctx.fill();ctx.strokeStyle=old?'rgba(172,129,87,.22)':ctx.fillStyle;ctx.lineWidth=old?.35:.5;ctx.stroke();
    }
    for(const m of markers){const p=point(m.at),x=w/2+p[0]*scale,y=h/2+p[1]*scale;ctx.beginPath();ctx.arc(x,y,10,0,2*Math.PI);ctx.fillStyle='#fff';ctx.fill();ctx.strokeStyle='#477c70';ctx.stroke();ctx.fillStyle='#31594e';ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText(String(comments[m.path]),x,y+4);ctx.textAlign='left';}
    ctx.fillStyle='#6d737d';ctx.font='11px system-ui';ctx.fillText('Drag to orbit · Alt + scroll to zoom',14,h-15);
  }
  const schedule=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(draw);};
  const selectAt=(x,y)=>{for(const f of [...faces].reverse()){if(f.mesh.previous)continue;const [a,b,c]=f.p;const sign=(p,q)=>(x-q[0])*(p[1]-q[1])-(p[0]-q[0])*(y-q[1]);const signs=[sign(a,b),sign(b,c),sign(c,a)];if(signs.every(v=>v>=0)||signs.every(v=>v<=0)){selected=f.mesh.path;schedule();onSelect(selected);break;}}};
  canvas.onpointerdown=e=>{pressed={x:e.clientX,y:e.clientY,ox:e.clientX,oy:e.clientY};canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{if(!pressed)return;yaw+=(e.clientX-pressed.x)*.008;pitch=Math.max(0,Math.min(Math.PI/2,pitch+(e.clientY-pressed.y)*.008));pressed.x=e.clientX;pressed.y=e.clientY;schedule();};
  canvas.onpointerup=e=>{if(pressed&&Math.hypot(e.clientX-pressed.ox,e.clientY-pressed.oy)<4){const r=canvas.getBoundingClientRect();selectAt(e.clientX-r.left,e.clientY-r.top);}pressed=null;};
  const magnify=factor=>{zoom=Math.max(.8,Math.min(1.5,zoom*factor));schedule();};
  canvas.onwheel=e=>{if(!e.altKey)return;e.preventDefault();magnify(Math.exp(-e.deltaY*.001));};
  const observer=new ResizeObserver(schedule);observer.observe(canvas);
  const view=name=>{[yaw,pitch]=name==='top'?[0,Math.PI/2]:name==='front'?[0,0]:[-.65,.75];schedule();};if(typeof initial==='object'&&initial){yaw=initial.yaw;pitch=Math.max(0,Math.min(Math.PI/2,initial.pitch));zoom=Math.max(.8,Math.min(1.5,initial.zoom));schedule();}else view(initial);
  return {view,zoom:magnify,camera:()=>({yaw,pitch,zoom}),select:path=>{selected=path;schedule();},destroy:()=>{closed=true;observer.disconnect();cancelAnimationFrame(frame);canvas.onpointerdown=canvas.onpointermove=canvas.onpointerup=canvas.onwheel=null;}};
}
