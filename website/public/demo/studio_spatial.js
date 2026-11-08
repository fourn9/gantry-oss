import {parseMesh,mountMesh} from './studio_mesh.js?v=spatial-20261108';
import {meshFile} from './studio_model.js?v=spatial-20261108';
import {spatialPaths} from './studio_artifacts.js?v=spatial-20261108';
import {esc as e} from './ui.js?v=spatial-20261108';

// Owns only the assembly preview. Expanding keeps the original viewer and draft DOM.
export function createSpatialContext({api,bytes}){
 let generation=0,mini,large,saved,selection,meshes=[],choose,camera,expanded,returnFocus;
 const root=()=>document.getElementById('studio-spatial');
 function restore(){
  large?.destroy();large=null;
  if(expanded){for(const [el,hidden] of expanded.children)el.hidden=hidden;expanded.panel.remove();expanded=null;returnFocus?.focus({preventScroll:true});}
 }
 function clear(){generation++;restore();if(mini)camera=mini.camera();mini?.destroy();mini=null;saved=null;meshes=[];if(root())root().replaceChildren();}
 async function set(stateId,path,nodeId,onChoose){
  const token=++generation;restore();if(mini)camera=mini.camera();mini?.destroy();mini=null;choose=onChoose;meshes=[];
  const host=root();if(!host)return;
  host.innerHTML='<div class="spatial-heading">Assembly</div><div class="spatial-loading" role="status">Loading saved model…</div>';
  try{
   const value=await api('get_development_state',{state_id:stateId});if(token!==generation)return;
   const paths=Object.keys(value.manifest).filter(meshFile);
   if(!paths.length){host.innerHTML='<p class="studio-small">No saved assembly preview.</p>';return;}
   if(paths.length>12)throw new Error('Assembly has more than 12 mesh files. Open an individual file.');
   const loaded=[];let count=0;
   for(const p of paths){const triangles=parseMesh(await bytes(value,p),p);if(token!==generation)return;count+=triangles.length;if(count>80000)throw new Error('Assembly preview exceeds the triangle limit.');loaded.push({path:p,triangles});}
   if(token!==generation||!host.isConnected)return;
   saved=value;meshes=loaded;selection=spatialPaths(value,path,nodeId);
   const labels=selection.map(p=>value.state.hierarchy.find(n=>n.paths?.includes(p))?.title||p.split('/').pop());
   host.innerHTML=`<div class="spatial-heading"><span>Assembly</span><button type="button" data-spatial="expand" aria-label="Expand assembly">Open 3D ↗</button></div><canvas id="spatial-canvas" tabindex="0" aria-label="Saved assembly. Drag to orbit; use the part selector to choose a component."></canvas><div class="spatial-selection">${e(labels.join(' + ')||'No part mapping')}</div><div class="spatial-controls"><label class="sr-only" for="spatial-part">Select a saved assembly part</label><select id="spatial-part"><option value="">Select a part…</option>${paths.map(p=>`<option value="${e(p)}" ${selection.length===1&&selection[0]===p?'selected':''}>${e(value.state.hierarchy.find(n=>n.paths?.includes(p))?.title||p.split('/').pop())}</option>`).join('')}</select><button type="button" data-spatial="reset" aria-label="Reset assembly view">↺</button></div>`;
   mini=mountMesh(host.querySelector('canvas'),meshes,p=>choose?.(p),camera,{},true);mini.select(selection);
  }catch(error){if(token===generation&&host.isConnected)host.innerHTML=`<div class="spatial-heading">Assembly</div><p class="studio-small">${e(error.message)}</p>`;}
 }
 function expand(){
  const target=document.getElementById('studio-file-content')||document.getElementById('studio-artifact')||document.getElementById('library-preview')||document.getElementById('main');
  if(!target||!saved||!meshes.length||expanded)return;
  returnFocus=document.activeElement;
  const children=[...target.children].map(el=>[el,el.hidden]);for(const [el] of children)el.hidden=true;
  const panel=document.createElement('section');panel.className='spatial-expanded';panel.innerHTML='<div class="studio-filebar"><strong>Assembly</strong><button type="button" data-spatial="return">← Back to file</button></div><div class="studio-cad"><canvas tabindex="0" aria-label="Expanded saved assembly"></canvas></div><p class="studio-small">Saved mesh preview · Select a part to highlight it.</p>';
  target.append(panel);expanded={children,panel};
  large=mountMesh(panel.querySelector('canvas'),meshes,p=>large.select(p),mini?.camera());large.select(selection);panel.querySelector('button').focus();
 }
 document.addEventListener('click',event=>{const b=event.target.closest('[data-spatial]');if(!b)return;const action=b.dataset.spatial;if(action==='expand')expand();if(action==='return')restore();if(action==='reset'){mini?.view('iso');camera=null;}});
 document.addEventListener('change',event=>{if(event.target.id==='spatial-part'&&event.target.value)choose?.(event.target.value);});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&expanded){event.preventDefault();restore();}});
 return {set,clear,restore};
}
