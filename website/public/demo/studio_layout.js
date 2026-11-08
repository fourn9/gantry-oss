import {mountStructureCamera} from './studio_camera.js?v=spatial-20261108';
import {esc as e} from './ui.js?v=spatial-20261108';

// The graph uses only recorded parent relations. Leaves are stacked per branch.
function layoutTree(nodes){
  const root=nodes.find(n=>!n.parent);if(!root)return {width:1,height:1,nodes:[],edges:[]};
  const children=id=>nodes.filter(n=>n.parent===id),groups=children(root.id),placed=[],edges=[];
  const width=Math.max(280,groups.length*208+32);let maxY=130;
  placed.push({...root,x:(width-184)/2,y:24});
  for(const [i,g] of groups.entries()){
    const x=32+i*208;placed.push({...g,x,y:136});edges.push([root.id,g.id]);let y=216;
    const seen=new Set([root.id,g.id]);
    function visit(parent,depth){for(const n of children(parent)){if(seen.has(n.id))continue;seen.add(n.id);placed.push({...n,x:x+Math.min(depth,2)*10,y});edges.push([parent,n.id]);y+=60;visit(n.id,depth+1);}}
    visit(g.id,0);maxY=Math.max(maxY,y);
  }
  return {width,height:maxY+24,nodes:placed,edges};
}
export function graphLayout(nodes){
  const ids=new Set(nodes.map(n=>n.id)),roots=nodes.filter(n=>!n.parent||!ids.has(n.parent));
  let width=0,height=1;const placed=[],edges=[];
  for(const root of roots){
    const members=[],pending=[root],seen=new Set();
    while(pending.length){const n=pending.pop();if(seen.has(n.id))continue;seen.add(n.id);members.push(n.id===root.id?{...n,parent:null}:n);pending.push(...nodes.filter(c=>c.parent===n.id).reverse());}
    const tree=layoutTree(members);placed.push(...tree.nodes.map(n=>({...n,x:n.x+width})));edges.push(...tree.edges);width+=tree.width+32;height=Math.max(height,tree.height);
  }
  return {width:Math.max(1,width-32),height,nodes:placed,edges};
}
export function graphMarkup(project,selected){
  const g=graphLayout(project.hierarchy||[]),by=new Map(g.nodes.map(n=>[n.id,n]));
  const edges=g.edges.map(([a,b])=>{const p=by.get(a),c=by.get(b);const x=p.x+92,y=p.y+48,tx=c.x+92,ty=c.y;return p.parent?`<path d="M${p.x} ${p.y+24} H${c.x-12} V${c.y+24} H${c.x}"/>`:`<path d="M${x} ${y} V${(y+ty)/2} H${tx} V${ty}"/>`;}).join('');
  return `<div class="structure-canvas-pane"><div class="structure-toolbar"><span>Product structure · ${g.nodes.length} nodes</span><div><button type="button" data-graph="out" aria-label="Zoom out structure">−</button><output id="graph-zoom">100%</output><button type="button" data-graph="in" aria-label="Zoom in structure">+</button><button type="button" data-graph="fit">Fit all</button><button type="button" data-graph="actual">100%</button></div></div><div id="structure-viewport" tabindex="0" aria-label="Product hierarchy diagram; pinch to zoom, drag to pan"><div id="structure-stage"><div id="structure-graph" data-project="${e(project.id||'')}" data-width="${g.width}" data-height="${g.height}" ><svg width="${g.width}" height="${g.height}" aria-hidden="true">${edges}</svg>${g.nodes.map(n=>`<button type="button" data-studio="component" data-value="${e(n.id)}" class="structure-card ${n.id===selected?.id?'selected':''}" data-x="${n.x}" data-y="${n.y}" aria-pressed="${n.id===selected?.id}" title="${e(n.title)}"><span>${e(n.title)}</span></button>`).join('')}</div></div></div><div class="structure-caption">Pinch to zoom · Drag or scroll to move · Click a component to inspect</div></div>`;
}
export function createStudioLayout(){
  let stopGraph=()=>{};const cameras=new Map();
  const root=document.documentElement;
  const clamp=(n,min,max)=>Math.min(Math.max(min,n),Math.max(min,max));
  function maxWidth(kind){return kind==='sidebar'?Math.max(200,Math.min(420,innerWidth-400)):Math.max(280,Math.min(560,innerWidth-(parseFloat(getComputedStyle(root).getPropertyValue('--studio-sidebar-width'))||240)-340));}
  function size(kind,value){const min=kind==='sidebar'?200:280,v=clamp(value,min,maxWidth(kind));root.style.setProperty(`--studio-${kind}-width`,v+'px');document.querySelectorAll(`[data-pane="${kind}"]`).forEach(h=>{h.setAttribute('aria-valuenow',String(Math.round(v)));h.setAttribute('aria-valuemax',String(maxWidth(kind)));});return v;}
  function handle(kind,label){const h=document.createElement('div');h.className='studio-pane-handle';h.dataset.pane=kind;h.tabIndex=0;h.role='separator';h.setAttribute('aria-label',label);h.setAttribute('aria-orientation','vertical');h.setAttribute('aria-valuemin',kind==='sidebar'?'200':'280');h.title='Drag to resize · Arrow keys to adjust · Double-click to reset';return h;}
  const side=document.querySelector('.sidebar');if(side&&!side.querySelector('[data-pane]'))side.append(handle('sidebar','Resize navigation sidebar'));
  document.addEventListener('pointerdown',event=>{
    const h=event.target.closest('[data-pane]');if(!h||event.button!==0||innerWidth<=760)return;
    const kind=h.dataset.pane,start=event.clientX,value=parseFloat(getComputedStyle(root).getPropertyValue(`--studio-${kind}-width`))||(kind==='sidebar'?240:340);
    event.preventDefault();h.setPointerCapture(event.pointerId);document.body.classList.add('studio-resizing');
    const move=ev=>size(kind,value+(ev.clientX-start)*(kind==='sidebar'?1:-1));
    const end=()=>{document.body.classList.remove('studio-resizing');h.removeEventListener('pointermove',move);h.removeEventListener('pointerup',end);h.removeEventListener('pointercancel',end);h.removeEventListener('lostpointercapture',end);};
    h.addEventListener('pointermove',move);h.addEventListener('pointerup',end);h.addEventListener('pointercancel',end);h.addEventListener('lostpointercapture',end);
  });
  document.addEventListener('keydown',event=>{
    const h=event.target.closest('[data-pane]');if(!h||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();const kind=h.dataset.pane,current=Number(h.getAttribute('aria-valuenow'));
    size(kind,event.key==='Home'?0:event.key==='End'?maxWidth(kind):current+(event.key==='ArrowRight'?16:-16)*(kind==='sidebar'?1:-1));
  });
  document.addEventListener('dblclick',event=>{const h=event.target.closest('[data-pane]');if(h)size(h.dataset.pane,h.dataset.pane==='sidebar'?240:340);});
  window.addEventListener('resize',()=>{for(const k of ['sidebar','detail'])size(k,parseFloat(getComputedStyle(root).getPropertyValue(`--studio-${k}-width`))||(k==='sidebar'?240:340));});
  document.addEventListener('click',event=>{const b=event.target.closest('[data-tree]');if(b)document.querySelectorAll('#sidebar-projects details').forEach(d=>d.open=b.dataset.tree==='expand');});
  const drawerSiblings=()=>document.querySelectorAll('.sidebar,.topbar,.demo-banner,.studio-content,.library-content,.library-toolbar,.studio-work-switch');
  function drawer(){
    const panel=document.querySelector('#studio-conversation,.library-panel');
    const narrow=innerWidth<=1024&&Boolean(panel);
    drawerSiblings().forEach(el=>el.inert=narrow);
    if(panel){if(narrow){panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');if(!panel.contains(document.activeElement))panel.focus({preventScroll:true});}else{panel.removeAttribute('role');panel.removeAttribute('aria-modal');}}
    return narrow?panel:null;
  }
  document.addEventListener('keydown',event=>{
    if(event.key!=='Tab')return;const panel=drawer();if(!panel)return;
    const items=[...panel.querySelectorAll('a[href],button:not(:disabled),input,textarea,select,[tabindex="0"]')].filter(el=>el.getClientRects().length);
    if(!items.length)return;const first=items[0],last=items.at(-1);
    if(!panel.contains(document.activeElement)||(event.shiftKey&&document.activeElement===first)){event.preventDefault();(event.shiftKey?last:first).focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  });
  window.addEventListener('resize',drawer);
  function mount(){
    stopGraph();drawer();
    for(const selector of ['.structure-inspector','#studio-conversation','.library-panel']){const p=document.querySelector(selector);if(p&&!p.querySelector('[data-pane]'))p.prepend(handle('detail','Resize detail panel'));}
    for(const k of ['sidebar','detail'])size(k,parseFloat(getComputedStyle(root).getPropertyValue(`--studio-${k}-width`))||(k==='sidebar'?240:340));
    const v=document.querySelector('#structure-viewport'),g=document.querySelector('#structure-graph');if(!v||!g)return;
    const w=Number(g.dataset.width),h=Number(g.dataset.height);
    g.style.width=w+'px';g.style.height=h+'px';
    g.querySelectorAll('.structure-card').forEach(card=>{card.style.left=card.dataset.x+'px';card.style.top=card.dataset.y+'px';});
    const key=g.dataset.project+':'+w+':'+h;
    const previous=cameras.get(key),saved=previous?{...previous.camera,x:previous.camera.x+(v.clientWidth-previous.width)/2,y:previous.camera.y+(v.clientHeight-previous.height)/2}:null;
    stopGraph=mountStructureCamera(v,g,document.querySelector('.structure-toolbar'),saved,camera=>cameras.set(key,{camera,width:v.clientWidth,height:v.clientHeight}));
  }
  return {mount,leave:()=>{stopGraph();drawerSiblings().forEach(el=>el.inert=false);}};
}
