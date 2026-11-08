import {parseMesh,mountMesh} from '../demo/studio_mesh.js?v=spatial-20261108';
import {createDemoAPI} from '../demo/demo-data.js?v=spatial-20261108';
import {esc} from '../demo/ui.js?v=spatial-20261108';
import {mountProjectMap} from './lp-project-map.js?v=spatial-20261108';
// Present the same renderers and sample data as the working Studio demo.
// Studio excerpts are inert. A clearly labelled, local sample replay adds
// activity summaries; it does not run or connect to live agents.
function mount(id,html){
 const host=document.getElementById(id);
 if(!host)return;
 const root=host.attachShadow({mode:'open'});
 root.innerHTML=`<link rel="stylesheet" href="/demo/style.css?v=spatial-20261108"><link rel="stylesheet" href="/demo/studio.css?v=spatial-20261108"><style>
 :host{display:block;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#252724;--bg:#fff;--sidebar:#f7f7f6;--soft:#f6f6f5;--hover:#efefed;--line:#e6e6e3;--text:#252724;--muted:#70746c;--accent:#2b6ddd;--green:#34835d;--red:#ad4c47;--amber:#927236;--radius:7px;--mono:ui-monospace,monospace}
 *{box-sizing:border-box}.excerpt{background:#fff;padding:18px;min-width:0}.studio-request{margin:0;border:0;padding:0;background:#fff}.studio-request-label{display:none}.studio-request h2{font-size:18px;line-height:1.3}.studio-request-main{display:block}.studio-request-main>button{margin-top:12px}.studio-request-details{margin-top:18px}.studio-request-details dl{grid-template-columns:1fr!important;gap:12px}.studio-request-details dd{font-size:12px;line-height:1.55}.studio-request-head{font-size:10px}.studio-request-actions,.studio-request-details>p{display:none}.studio-request-details summary{font-size:11px}.studio-workcolumns,.studio-workgridrow{grid-template-columns:minmax(0,1.2fr) minmax(0,1fr) 56px!important;gap:12px!important}.studio-scope,.studio-workcolumns>span:nth-child(3){display:none}.studio-workgridrow{padding:20px 0!important}.studio-workrow strong{font-size:13px;line-height:1.4}.studio-owner{font-size:11px;overflow-wrap:anywhere}.studio-owner small,.studio-status,.studio-workcolumns{font-size:10px}.excerpt-title{font-size:16px;font-weight:500;margin:0 0 8px}.excerpt-project{font-size:11px;color:#70746c;margin:0 0 20px}.studio-worklist{border:0}button,summary,a{cursor:default}.studio-small{font-size:11px}
 @media(max-width:680px){.excerpt{padding:15px}.studio-workcolumns,.studio-workgridrow{gap:8px!important}.studio-workrow strong{font-size:12px}}

 .sender{display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:18px}.agent-avatar{width:29px;height:29px;display:grid;place-items:center;background:#edf5ed;color:#39764a;border:1px solid #d2e4d4;border-radius:50%;font:11px var(--mono);flex:none}.sender strong{font-size:12px;font-weight:600}.sender small{display:block;color:var(--muted);font-size:10px;margin-top:2px}.sender .sender-tag{margin-left:auto;color:#39764a;font-size:10px;white-space:nowrap}.status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#449363;margin-right:6px;vertical-align:1px}
 .saved-preview{display:grid;grid-template-columns:115px minmax(0,1fr);gap:16px}.saved-preview aside{border-right:1px solid var(--line);padding-right:8px}.saved-preview canvas{width:100%;height:160px}.saved-preview small,.excerpt-discussion small{font-size:10px;color:var(--muted)}.saved-preview pre{font-size:11px;white-space:pre-wrap;line-height:1.8;overflow-wrap:anywhere}.file-title{font-size:11px;padding:0 0 12px;border-bottom:1px solid var(--line)}.excerpt-discussion{border-top:1px solid var(--line);padding-top:14px;margin-top:16px;font-size:11px}.excerpt-discussion>span{font-weight:500}.excerpt-discussion p{margin:10px 0}.saved-preview section{min-width:0}@media(max-width:420px){.saved-preview{grid-template-columns:90px minmax(0,1fr);gap:10px}}
 </style><div class="excerpt" inert>${html}</div>`;
 root.querySelectorAll('details').forEach(d=>d.open=true);
 host.querySelector('.lp-screen-fallback')?.remove();
 return root;
}
try{
 const {api}=await createDemoAPI();
 const detail=await api('studio_work',{work_id:'bracket'});
 const path='sensor/calibration.yaml',part=await api('read_artifact_chunk',{revision_id:detail.selected.state.snapshot,path,index:0});
 const ledger=mount('lp-ledger-screen',`<div class="excerpt-project">Desktop robot arm / Sensor bracket</div><div class="saved-preview"><aside><small>Assembly</small><canvas aria-label="Saved sensor bracket location"></canvas><small>Sensor bracket</small></aside><section><div class="file-title">${esc(path)}</div><pre>${esc(atob(part.content))}</pre></section></div><div class="excerpt-discussion"><span>Discussion</span><p><strong>Sam Rivera</strong> · @Alex Morgan Please confirm the sensor offset.</p><small>Illustrative saved file and conversation</small></div>`);
 const meshes=[];for(const path of Object.keys(detail.selected.manifest).filter(p=>p.endsWith('.stl'))){const part=await api('read_artifact_chunk',{revision_id:detail.selected.state.snapshot,path,index:0});meshes.push({path,triangles:parseMesh(Uint8Array.from(atob(part.content),c=>c.charCodeAt(0)),path)});}
 if(ledger){const mesh=mountMesh(ledger.querySelector('canvas'),meshes,()=>{},'iso',{},true);mesh.select('cad/sensor-bracket.stl');}
 const overview=await api('studio_overview');
 mountProjectMap(document.getElementById('lp-crew-screen'),overview,detail);
}catch(error){console.warn('Studio excerpts unavailable; the demo links remain available.',error);}
