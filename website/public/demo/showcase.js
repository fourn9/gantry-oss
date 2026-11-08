if(location.hash.startsWith('#studio')) location.replace('./workspace.html'+location.hash);
import {createDemoAPI} from './demo-data.js?v=spatial-20261108';
import * as view from './studio_views.js?v=spatial-20261108';
import {lineDiff} from './studio_model.js?v=spatial-20261108';
import {parseMesh,mountMesh} from './studio_mesh.js?v=spatial-20261108';
import {esc} from './ui.js?v=spatial-20261108';
import * as library from './studio_library_views.js?v=spatial-20261108';
// Reuse the actual Studio renderers and invented demo data. Each excerpt has
// isolated styles and inert controls; the adjacent link opens the working demo.
function excerpt(id,html){
 const host=document.getElementById(id),root=host.attachShadow({mode:'open'});
 root.innerHTML=`<link rel="stylesheet" href="./style.css?v=spatial-20261108"><link rel="stylesheet" href="./studio.css?v=spatial-20261108"><link rel="stylesheet" href="./demo.css?v=spatial-20261108"><style>
 :host{display:block;color:#252724;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--bg:#fff;--sidebar:#f7f7f6;--soft:#f6f6f5;--hover:#efefed;--line:#e6e6e3;--text:#252724;--muted:#70746c;--accent:#2b6ddd;--green:#34835d;--red:#ad4c47;--amber:#927236;--radius:7px;--mono:ui-monospace,monospace}
 .studio-request{display:none}.studio-workrow p{font-size:12px;line-height:1.7}.screen{background:white;min-height:340px;overflow:hidden}.studio-body{min-height:0;display:block}.studio-conversation{border:0;padding:24px;min-height:360px}.studio-threadhead{position:static}.studio-part-list{display:none!important}.studio-structure>.studio-map{display:block!important;overflow:hidden}.studio-map svg{width:100%;min-width:0;height:auto;max-height:330px}.studio-workhead{padding:20px 24px}.studio-workhead h1{font-size:18px}.studio-artifactbar{padding:10px 16px;flex-wrap:nowrap}.studio-artifactbar .studio-actions{width:auto}.studio-viewer{padding:18px}.studio-cad canvas{display:block;width:100%;height:320px}.studio-code-line{font-size:12px!important}.studio-checks{font-size:12px}.studio-small{font-size:11px}.studio-back{display:none}.studio-workfoot{padding:12px 18px}.studio-messages{max-height:none}.component-excerpt{display:grid;grid-template-columns:170px minmax(0,1fr);min-height:340px}.component-excerpt>aside{background:#f7f7f6;padding:18px 12px;border-right:1px solid #e6e6e3}.component-excerpt>section{padding:16px;min-width:0}.component-excerpt .studio-workcolumns{display:none}.component-excerpt .studio-workgridrow{display:flex;flex-direction:column;align-items:flex-start;gap:8px}.component-excerpt .studio-view-controls,.component-excerpt .studio-breadcrumb>a,.component-excerpt .studio-breadcrumb>span{display:none}.component-excerpt .studio-tree-node{margin-left:8px}.component-excerpt .studio-projectbar{padding-bottom:18px}@media(max-width:600px){.component-excerpt{grid-template-columns:145px minmax(0,1fr)}}button{cursor:default}.studio-content{min-width:0}.hero-workspace{display:grid;grid-template-columns:180px minmax(0,1fr)}.hero-tree{padding:20px 12px;border-right:1px solid var(--line);background:var(--sidebar)}.hero-workspace .studio-body.conversation-open{display:grid;grid-template-columns:minmax(0,1fr) 240px;min-height:480px}.hero-workspace .studio-conversation{position:static!important;height:auto!important;width:auto!important;min-height:0;box-shadow:none;padding:15px;border-left:1px solid var(--line);border-top:0}.hero-workspace .studio-actions{display:none}.hero-workspace .studio-workhead{padding:20px}.hero-workspace .studio-work-location{display:none}.hero-workspace .studio-comparebar{display:none}.hero-workspace .studio-artifactbar{padding:12px}.hero-tree .studio-tree{margin-left:0}.hero-tree .mini-model{margin-top:20px;border-top:1px solid var(--line);padding-top:14px}.hero-tree canvas{height:170px;width:100%;display:block}.hero-tree small,.excerpt-message small{font-size:10px;color:var(--muted)}.excerpt-calibration{font-size:12px;line-height:2;white-space:pre-wrap;overflow-wrap:anywhere;padding:18px 4px}.excerpt-message{font-size:12px;line-height:1.8;margin-top:20px}.excerpt-message p{margin:12px 0}.hero-workspace .studio-threadhead{position:static}@media(max-width:760px){.hero-workspace{grid-template-columns:130px minmax(0,1fr)}.hero-workspace .studio-body.conversation-open{display:block}.hero-workspace .studio-conversation{display:none}.hero-tree{padding:12px 4px}.hero-tree .studio-tree-link{font-size:10px;padding:5px}.hero-workspace .studio-workhead h1{font-size:14px}.excerpt-calibration{font-size:11px}.hero-tree canvas{height:130px}}
 </style><div class="screen studio-mode" inert>${html}</div>`;
 return root;
}
try{
 const {api}=await createDemoAPI(),overview=await api('studio_overview'),detail=await api('studio_work',{work_id:'bracket'});
 async function bytes(state,path){const part=await api('read_artifact_chunk',{revision_id:state.state.snapshot,path,index:0});return Uint8Array.from(atob(part.content),c=>c.charCodeAt(0));}
 const incoming=await api('studio_inbox');excerpt('screen-inbox',view.inbox(incoming.items));
 const project=overview.projects[0],sensor=project.hierarchy.find(n=>n.id==='sensor'),side=view.sidebar(overview,[],{project:project.id,component:sensor.id});
 const hero=excerpt('screen-cad',`<div class="hero-workspace"><aside class="hero-tree">${side.projects}<div class="mini-model"><small>Assembly · Sensor bracket</small><canvas aria-label="Saved assembly location"></canvas></div></aside><section>${view.workDetail(detail,{tab:'code',compare:true,compareState:'state_base',panel:'discussion'})}</section></div>`);
 const calibrationPath='sensor/calibration.yaml';
 const savedCalibration=new TextDecoder().decode(await bytes(detail.selected,calibrationPath));
 hero.querySelector('#studio-artifact').innerHTML=`<div class="studio-filebar">${calibrationPath}<small>Modified</small></div><pre class="excerpt-calibration">${esc(savedCalibration)}</pre>`;
 hero.querySelector('#studio-conversation').innerHTML=`<div class="library-panel-tabs"><button>References</button><button aria-pressed="true">Discussion</button></div><div class="excerpt-message"><strong>Sam Rivera</strong><p>@Alex Morgan Please confirm the sensor offset against the saved bracket geometry.</p><small>Illustrative conversation</small></div>`;
 const meshes=[];for(const path of Object.keys(detail.selected.manifest).filter(p=>p.endsWith('.stl')))meshes.push({path,triangles:parseMesh(await bytes(detail.selected,path),path)});
 const mesh=mountMesh(hero.querySelector('canvas'),meshes,()=>{},'iso',{},true);mesh.select('cad/sensor-bracket.stl');
 const p=overview.projects[0],n=p.hierarchy.find(n=>n.id==='sensor'),tree=view.sidebar(overview,[],{project:p.id,component:n.id});
 excerpt('screen-structure',`<div class="component-excerpt"><aside>${tree.projects}</aside><section>${view.projectHeader(p,n,'work')}${view.workList([detail.work])}</section></div>`);
 const savedFiles=await api('studio_library',{project_id:'bench',section:'files'});
 const savedText=new TextDecoder().decode(await bytes(await api('get_development_state',{state_id:savedFiles.state.id}),'control/motion.py'));
 excerpt('screen-files',view.projectHeader(overview.projects[0],overview.projects[0].hierarchy.find(n=>n.id==='control'),'files')+`<div class="library-toolbar"><select aria-label="Saved file"><option>control/motion.py</option></select><div class="studio-actions"><button>Baseline</button><button>References</button><button>Discussion</button></div></div><div class="studio-code" style="padding:24px"><pre>${esc(savedText)}</pre></div>`);
 const requirements=await api('studio_library',{project_id:'bench',state_id:'state_bracket_v1',section:'requirements'});
 excerpt('screen-requirements',view.projectHeader(overview.projects[0],null,'requirements')+library.requirementDetail(requirements.items.find(r=>r.requirement_id==='settling-time')));
 const baseline=await api('get_development_state',{state_id:detail.versions[0].id});
 const path='control/motion.py';const before=new TextDecoder().decode(await bytes(baseline,path)),after=new TextDecoder().decode(await bytes(detail.selected,path));
 const rows=lineDiff(before,after);
 const diff=excerpt('screen-compare',view.workDetail(detail,{tab:'code',compare:true,compareState:baseline.state.id}));
 diff.querySelector('.studio-workhead').remove();
 diff.querySelector('#studio-artifact').innerHTML=`<div class="studio-filebar">${esc(path)}</div><div class="studio-code">${rows.map(r=>`<div class="studio-code-line ${r.kind}"><span>${r.before||''}</span><span>${r.after||''}</span><span>${r.kind==='add'?'+':r.kind==='remove'?'−':' '}</span><code>${esc(r.text)||' '}</code></div>`).join('')}</div>`;
 const thread=detail.threads[0];
 excerpt('screen-conversation',`<aside class="studio-conversation">${view.conversation(detail,{anchor:thread.anchor,state_id:thread.state_id,thread_id:thread.id},'',[])}</aside>`);
 document.getElementById('conversation-link').href='./workspace.html#'+view.workURL('bracket',thread.state_id,thread.id);
 await api('demo_import_update',{work_id:'bracket',version:detail.work.version});
 const updated=await api('studio_work',{work_id:'bracket'});
 const checks=excerpt('screen-checks',view.workDetail(updated,{tab:'checks',compare:false}));
 checks.querySelector('#studio-artifact').innerHTML=view.checks(updated);
 document.querySelectorAll('.screen-loading').forEach(el=>el.remove());
}catch(error){document.querySelectorAll('.screen-loading').forEach(el=>el.textContent='Open the interactive demo to explore this feature.');console.error(error);}
