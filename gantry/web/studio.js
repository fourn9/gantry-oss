import {createStudioLayout} from './studio_layout.js';
import {createBotUI} from './studio_bot_ui.js';
import {$,esc as e,short,icon,download} from './ui.js';
import * as view from './studio_views.js';
import {cadFile,meshFile,codeFile,versionLabel,fileChanges,lineDiff,linesOf,relatedWorks,commentCount} from './studio_model.js';
import {parseMesh,mountMesh} from './studio_mesh.js';
import {createActivityMonitor} from './studio_activity.js';

export function createStudio({api,modal,toast,fail}){
  const layout=createStudioLayout();
  let onboarding,crewSetup;
  let overview,detail,project,node,viewEpoch=0,artifactEpoch=0,mesh,tab='cad',compare=false,compareState='',file='',selectedPart='',conversation=null,lastWork='',draft='',mentions=[],threadDetail;
  let downloadState=null,recent=[],cache=new Map(),drafts=new Map(),cameras=new Map(),meshKey='';
  const route=()=>location.hash.slice(1).split('/').map(x=>decodeURIComponent(x));
  const handles=()=>['studio','studio-work','studio-inbox','studio-recent','studio-start','studio-crew'].includes(route()[0]||'studio');
  const a=view.action;
  const activity=createActivityMonitor({api,notice:text=>{const el=$('#studio-live-notice');if(el){el.hidden=!text;el.querySelector('span').textContent=text;}}});
  function reset(){layout.leave();onboarding?.leave();crewSetup?.leave();activity.clear();viewEpoch++;artifactEpoch++;disposeMesh();cache.clear();drafts.clear();cameras.clear();overview=detail=undefined;recent=[];lastWork='';conversation=null;threadDetail=null;draft='';mentions=[];}
  function disposeMesh(){if(mesh){if(mesh.camera)cameras.set(meshKey,mesh.camera());mesh.destroy();mesh=null;while(cameras.size>50)cameras.delete(cameras.keys().next().value);}}
  function chooseFile(path){file=path;selectedPart=path;selectConversation(null);threadDetail=null;drawWork();}
  function remember(){if(conversation)drafts.set(JSON.stringify([detail.work.id,conversation]),{draft,mentions:[...mentions]});}
  function selectConversation(value){remember();conversation=value;const saved=drafts.get(JSON.stringify([detail.work.id,value]));draft=saved?.draft||'';mentions=saved?.mentions||[];}
  function sidebar(){const side=view.sidebar(overview,recent,{project:project?.id});$('#nav').innerHTML=side.nav;$('#sidebar-projects').innerHTML=side.projects;$('#recent-sessions').innerHTML=side.recent;}
  async function render(){
    layout.leave();
    onboarding?.leave();crewSetup?.leave();remember();activity.clear();const current=++viewEpoch,parts=route(),kind=parts[0]||'studio';artifactEpoch++;disposeMesh();
    document.body.classList.add('studio-mode');$('#main').className='studio-main';
    $('#main').innerHTML=view.hint('Loading workspace…');
    const loaded=await api('studio_overview');if(current!==viewEpoch||!handles())return;overview=loaded;activity.set('studio_overview',{},loaded);
    if(kind==='studio-start'){
      sidebar();if(!onboarding){const {createOnboarding}=await import('./onboarding.js');onboarding=createOnboarding({api,modal,toast,fail});}
      if(current!==viewEpoch)return;await onboarding.render(parts[1],overview);return;
    }
    if(kind==='studio-crew'){
      project=overview.projects.find(p=>p.sessions?.some(s=>s.id===parts[1]));node=null;
      sidebar();if(!crewSetup){const {createCrewSetup}=await import('./crew_setup.js');crewSetup=createCrewSetup({api,toast,fail});}
      if(current!==viewEpoch)return;await crewSetup.render(parts[1],parts[2]);return;
    }
    if(kind==='studio-work'){
      const value=await api('studio_work',{work_id:parts[1],...(parts[2]?{state_id:parts[2]}:{})});if(current!==viewEpoch||!handles())return;
      if(lastWork!==value.work.id){conversation=null;threadDetail=null;draft='';mentions=[];tab='cad';compare=false;file='';selectedPart='';lastWork=value.work.id;}
      detail=value;activity.set('studio_work',{work_id:value.work.id,activity_only:true},value);project=overview.projects.find(p=>p.id===detail.work.project_id);node=null;
      recent=[detail.work,...recent.filter(w=>w.id!==detail.work.id)].slice(0,30);
      if(parts[3]){const thread=value.threads.find(t=>t.id===parts[3]);threadDetail=null;if(thread){tab=thread.anchor.kind==='code'?'code':'cad';file=thread.anchor.path||'';selectedPart=thread.anchor.part||'';selectConversation({anchor:thread.anchor,state_id:thread.state_id,thread_id:thread.id});}}
      if(conversation&&conversation.state_id!==value.selected.state.id&&!parts[3]){selectConversation(null);threadDetail=null;}
      sidebar();$('#breadcrumb').innerHTML=project?view.projectHeader(project,null,'work'):'Work';
      await drawWork();if(current!==viewEpoch)return;if(parts[3])focusConversation();
      if(parts[4]&&detail.can_comment)api('studio_acknowledge',{notification_id:parts[4]}).catch(fail);
      return;
    }
    project=overview.projects.find(p=>p.id===parts[1])||overview.projects[0];node=project?.hierarchy.find(n=>n.id===parts[2]);sidebar();
    if(kind==='studio-inbox'){
      const inbox=await api('studio_inbox');if(current!==viewEpoch)return;activity.set('studio_inbox',{},inbox);$('#breadcrumb').textContent='Inbox';$('#main').innerHTML=view.inbox(inbox.items)+(inbox.next?a('more-inbox','Load more',inbox.next,'class="studio-more"'):'');return;
    }
    if(kind==='studio-recent'){$('#breadcrumb').textContent='Recent';$('#main').innerHTML='<div class="studio-page-title"><h1>Recent</h1><span class="studio-small">Work opened in this tab</span></div>'+view.workList(recent,'No recently opened work.');return;}
    if(!project){$('#breadcrumb').textContent='Projects';$('#main').innerHTML=view.hint('Start a shared project','Create a project, import saved files, then start work.')+(overview.can_import?'<div class="studio-empty">'+a('import-project','Import project')+'</div>':'');return;}
    const projectTab=parts[3]==='work'?'work':'structure';$('#breadcrumb').innerHTML=view.projectHeader(project,node,projectTab);
    $('#main').innerHTML=(projectTab==='structure'?view.structure(project,node,overview.works):
      '<div class="studio-list-tools">'+a('new-work','New work')+'</div>'+view.workList(relatedWorks(overview.works,project.id,node?.id,project.hierarchy)))+
      (overview.next?a('more-work','Load more work',overview.next,'class="studio-more"'):'');
    layout.mount();
  }
  function drawWork(){
    disposeMesh();
    const versions=detail.versions,index=versions.findIndex(v=>v.id===detail.selected.state.id);
    if(!versions.some(v=>v.id===compareState&&v.id!==detail.selected.state.id))compareState=versions[Math.max(0,index-1)]?.id;
    if(index===0)compare=false;
    $('#main').innerHTML=view.workDetail(detail,{tab,compare,compareState,conversation});
    drawConversation();layout.mount();const epoch=viewEpoch;const load=loadArtifact();const request=artifactEpoch;return load.catch(error=>{if(epoch===viewEpoch&&request===artifactEpoch&&$('#studio-artifact'))$('#studio-artifact').innerHTML=view.hint('Unable to load artifact',error.message);});
  }
  function drawConversation(){if(conversation&&$('#studio-conversation')){$('#studio-conversation').innerHTML=view.conversation(threadDetail||detail,conversation,draft,mentions);layout.mount();}}
  async function bytes(state,path,max=16*1024*1024){
    const info=state.manifest[path];if(!info)throw new Error('File not present in this version.');if(info.size>max)throw new Error('Preview size limit reached. Restore the saved file with the local adapter.');
    if(cache.has(info.hash))return cache.get(info.hash);
    if(!crypto.subtle)throw new Error('Verified previews require HTTPS or localhost.');
    const pieces=[];const hash=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(v=>v.toString(16).padStart(2,'0')).join('');
    for(let i=0;i<(info.chunks?.length||1);i++){const part=await api('read_artifact_chunk',{revision_id:state.state.snapshot,path,index:i});const raw=Uint8Array.from(atob(part.content),c=>c.charCodeAt(0));if(await hash(raw)!==part.hash)throw new Error('Artifact integrity check failed.');pieces.push(raw);}
    const raw=new Uint8Array(await new Blob(pieces).arrayBuffer());if(await hash(raw)!==info.hash)throw new Error('Artifact integrity check failed.');
    while([...cache.values()].reduce((n,x)=>n+x.length,0)+raw.length>32*1024*1024&&cache.size)cache.delete(cache.keys().next().value);cache.set(info.hash,raw);return raw;
  }
  const options=(paths,selected)=>paths.map(p=>{const count=commentCount(detail,detail.selected.state.id,p);return `<option value="${e(p)}" ${p===selected?'selected':''}>${e(p)}${count?' · '+count+' comment'+(count===1?'':'s'):''}</option>`;}).join('');
  async function loadArtifact(){
    const current=++artifactEpoch;disposeMesh();downloadState=null;const target=$('#studio-artifact'),v=detail.selected;
    if(tab==='checks'){target.innerHTML=view.checks(detail);return;}
    const old=compare?await api('get_development_state',{state_id:compareState}):null;if(current!==artifactEpoch)return;
    const match=tab==='cad'?cadFile:codeFile;const paths=[...new Set([...Object.keys(v.manifest),...(old?Object.keys(old.manifest):[])])].filter(match).sort();
    if(!paths.length){target.innerHTML=view.hint(tab==='cad'?'No shared CAD files':'No shared code files','Import saved files or connect your local adapter to this work.')+a('import-help','Connection instructions');return;}
    if(!paths.includes(file)){const changed=new Set(v.diffs.map(d=>d.path));file=paths.find(p=>changed.has(p)&&(tab!=='cad'||meshFile(p)))||paths.find(meshFile)||paths[0];}
    target.innerHTML=`<div class="studio-filebar"><select id="studio-file" aria-label="Artifact file">${options(paths,file)}</select><span class="studio-small">${e(short((v.manifest[file]||old?.manifest[file])?.hash))}</span></div><div id="studio-file-content" aria-live="polite">${view.hint('Loading saved version…')}</div>`;
    const body=$('#studio-file-content');
    downloadState=v.manifest[file]?v:old;
    if(tab==='cad'){
      if(!meshFile(file)){body.innerHTML=view.hint('Preview not supported for this format','The native source is saved. Export an STL or OBJ preview from your CAD tool and import it alongside the editable file.')+a('download-file','Download saved source',file)+a('import-help','Connect a CAD adapter');return;}
      const currentPaths=Object.keys(v.manifest).filter(meshFile);const previewPaths=currentPaths.length<=12?currentPaths:[file].filter(p=>v.manifest[p]);
      const meshes=[];let triangles=0;
      for(const p of previewPaths){const t=parseMesh(await bytes(v,p),p);triangles+=t.length;if(triangles>80000)throw new Error('Assembly preview is too large. Export a lighter mesh.');meshes.push({path:p,triangles:t});}
      if(old?.manifest[file])meshes.push({path:file,previous:true,triangles:parseMesh(await bytes(old,file),file)});
      if(current!==artifactEpoch)return;
      body.innerHTML=`<div class="studio-mesh-tools"><span class="studio-small">Selected part: ${e(file)}</span><div>${a('orientation','Isometric','iso')}${a('orientation','Top','top')}${a('orientation','Front','front')}${a('zoom','−','0.8','aria-label="Zoom out"')}${a('zoom','+','1.25','aria-label="Zoom in"')}</div></div><div class="studio-cad"><canvas id="studio-canvas" aria-label="Saved 3D mesh preview" tabindex="0"></canvas></div><div class="studio-caption"><span>${e(compare?'Current assembly · Amber: previous '+file:'Saved mesh preview · Coordinates and units as exported')}</span>${a('part-conversation',icon('sessions')+'Discuss this part'+(commentCount(detail,v.state.id,file)?' · '+commentCount(detail,v.state.id,file):''),'',!v.manifest[file]?'disabled':'')}</div>${!v.manifest[file]?'<p class="studio-small">This file was deleted in the selected version. Amber geometry is from the previous version.</p>':''}`;
      selectedPart=previewPaths.includes(file)?file:'';
      meshKey=detail.work.id+':'+v.state.id;mesh=mountMesh($('#studio-canvas'),meshes,chooseFile,cameras.get(meshKey),Object.fromEntries(previewPaths.map(p=>[p,commentCount(detail,v.state.id,p)])));mesh.select(selectedPart);return;
    }
    const read=async(st,p)=>st?.manifest[p]?new TextDecoder('utf-8',{fatal:true}).decode(await bytes(st,p,262144)):'';
    const text=await read(v,file),before=await read(old,file);if(current!==artifactEpoch)return;
    if(text.includes('\0')||before.includes('\0'))throw new Error('This file is binary. Use the external editor.');
    const rows=compare?lineDiff(before,text):linesOf(text).map((t,i)=>({text:t,after:i+1,kind:'same'}));
    const line=(r,side)=>`<button class="studio-code-line ${r.kind}" data-studio="line" data-value="${r.after||r.before}" data-side="${side||(!r.after?'before':'after')}"><span>${r.before||''}</span><span>${r.after||''}</span><span>${r.kind==='add'?'+':r.kind==='remove'?'−':' '}</span><code>${e(r.text)||' '}</code>${commentCount(detail,r.after?v.state.id:old?.state.id,file,r.after||r.before)?`<span class="studio-line-comments" title="Comments on this line">${icon('sessions')}${commentCount(detail,r.after?v.state.id:old?.state.id,file,r.after||r.before)}</span>`:''}</button>`;
    body.innerHTML=`<div class="studio-code-source studio-small">${e(detail.source?.repository||'Repository not recorded')}${detail.source?.commit?' · Source commit '+e(short(detail.source.commit)):''}</div><div class="studio-code" aria-label="Code and line comments">${rows?rows.slice(0,4000).map(r=>line(r)).join(''):`<p class="studio-small">Large comparison: separate versions</p><h2>Before</h2>${linesOf(before).slice(0,2000).map((text,i)=>line({text,before:i+1,kind:'remove'},'before')).join('')}<h2>After</h2>${linesOf(text).slice(0,2000).map((text,i)=>line({text,after:i+1,kind:'add'},'after')).join('')}`}</div><div class="studio-caption"><span>${compare?e(short(old.state.id))+' → ':''}${e(short(v.state.id))} · ${e(file)}</span><span>Select a line to discuss</span></div>${(rows?.length>4000||!rows)?'<p class="studio-small">Preview is limited; restore files to inspect the complete change.</p>':''}`;
    if(conversation?.anchor.kind==='code'&&conversation.anchor.path===file){const side=conversation.state_id===v.state.id?'after':'before';const row=body.querySelector(`[data-studio=line][data-side=${side}][data-value="${conversation.anchor.line}"]`);row?.classList.add('selected');row?.scrollIntoView({block:'nearest'});}
  }
  async function openConversation(anchor,stateId=detail.selected.state.id){
    const epoch=viewEpoch,artifact=artifactEpoch,wid=detail.work.id;
    const older=stateId===detail.selected.state.id?null:await api('studio_work',{work_id:wid,state_id:stateId});
    if(epoch!==viewEpoch||artifact!==artifactEpoch||detail.work.id!==wid||!handles())return;
    threadDetail=older;const source=threadDetail||detail;
    const t=source.threads.find(t=>JSON.stringify(Object.entries(t.anchor).sort())===JSON.stringify(Object.entries(anchor).sort()));
    selectConversation({anchor,state_id:stateId,...(t?{thread_id:t.id}:{})});await drawWork();if(epoch!==viewEpoch)return;focusConversation();
  }
  function focusConversation(){const panel=$('#studio-conversation');if(!panel)return;if(globalThis.innerWidth<=1024)panel.scrollIntoView({block:'start'});panel.focus({preventScroll:true});}
  async function closeConversation(){selectConversation(null);threadDetail=null;const epoch=viewEpoch;await drawWork();if(epoch!==viewEpoch)return;const target=$('#studio-canvas')||$('#studio-artifact');if(globalThis.innerWidth<=1024)target?.scrollIntoView({block:'start'});target?.focus({preventScroll:true});}
  async function loadUpdates(){
    if(route()[0]!=='studio-work')return render();
    const epoch=viewEpoch,artifact=artifactEpoch,wid=detail.work.id,sid=detail.selected.state.id;
    const current=()=>epoch===viewEpoch&&artifact===artifactEpoch;
    const value=await api('studio_work',{work_id:wid,state_id:sid});
    if(!current())return;
    const old=conversation&&conversation.state_id!==sid?await api('studio_work',{work_id:wid,state_id:conversation.state_id}):null;
    if(!current())return;
    remember();detail=value;threadDetail=old;activity.set('studio_work',{work_id:wid,activity_only:true},value);drawWork();
  }
  async function share(){
    const epoch=viewEpoch,wid=detail.work.id,selectedId=detail.selected.state.id;
    const value=await api('studio_work',{work_id:wid});if(epoch!==viewEpoch)return;const current=value.selected;
    if(current.state.id!==selectedId)throw new Error('Work advanced. Refresh and inspect the latest checkpoint before sharing.');
    const earlier=[...value.versions].reverse().find(v=>v.id!==current.state.id&&v.sharing==='shared')||value.versions[0];const prior=await api('get_development_state',{state_id:earlier.id});if(epoch!==viewEpoch)return;
    const changes=fileChanges(prior.manifest,current.manifest);
    modal('Share update',`<p>${e(value.work.title)} · ${e(versionLabel(earlier))} → ${e(versionLabel(value.versions.at(-1)))}</p><div class="studio-share-files">${changes.map(c=>`<div><span>${e(c.path)}<small>${e(c.kind)}</small></span><span title="${e(c.before||'Not present')} → ${e(c.after||'Deleted')}">${e(c.before?short(c.before):'New')} → ${e(c.after?short(c.after):'Deleted')}</span></div>`).join('')||'<p>No file changes; checkpoint context may have changed.</p>'}</div><label>Update note<textarea name="note" maxlength="1000" placeholder="What changed? What remains unfinished?"></textarea></label><p>Share this work-in-progress version. This does not adopt it or mark checks as passed.</p>`,async form=>{await api('studio_share_update',{work_id:value.work.id,version:value.work.version,state_id:current.state.id,note:form.note.value});toast('Update shared · Not formally adopted');await render();},'Share update');
  }
  async function importFiles(){
    if(!detail.can_update||detail.selected.state.id!==detail.work.head)throw new Error('This work is read-only for your identity.');
    const captured=detail;
    modal('Import saved changes',`<p>Save your edits in the external tool first.</p><label>Saved files<input type="file" name="files" multiple required></label><div id="studio-import-paths"></div><label>Checkpoint note<input name="summary" required maxlength="1000" placeholder="What changed?"></label><p>Only selected files are imported. Other saved files are retained. Unsaved external edits are not acquired.</p>`,async form=>{
      const files=[...form.files.files];if(!files.length||files.length>200||files.reduce((n,f)=>n+f.size,0)>48*1024*1024)throw new Error('Choose 1–200 files, up to 48 MiB total.');
      const values={};for(let i=0;i<files.length;i++){const f=files[i],path=form.elements['path'+i].value.trim();if(f.size>32*1024*1024)throw new Error('File exceeds 32 MiB.');if(values[path])throw new Error('Duplicate target path.');const raw=new Uint8Array(await f.arrayBuffer());let binary='';for(let n=0;n<raw.length;n+=32768)binary+=String.fromCharCode(...raw.subarray(n,n+32768));values[path]=btoa(binary);}
      const result=await api('studio_import_update',{work_id:captured.work.id,version:captured.work.version,files:values,summary:form.summary.value});file='';toast('Saved as an unshared checkpoint');location.hash=view.workURL(captured.work.id,result.state.id);
    },'Import checkpoint');
    document.querySelector('#dialog [name=files]').onchange=event=>{const paths=Object.keys(captured.selected.manifest);$('#studio-import-paths').innerHTML=[...event.target.files].map((f,i)=>{const matching=paths.filter(p=>p.split('/').pop()===f.name);return `<label>Target path for ${e(f.name)}<input name="path${i}" required value="${e(matching.length===1?matching[0]:f.webkitRelativePath||f.name)}"></label>`;}).join('');};
  }
  function importProject(){location.hash='#studio-start';}
  const botUI=createBotUI({api,modal,toast,getContext:()=>({project,detail:threadDetail||detail,selection:conversation,draft,epoch:viewEpoch}),refresh:loadUpdates});
  const handlers={
    ...botUI.handlers,
    tab:async value=>{remember();selectConversation(null);threadDetail=null;tab=value;file='';drawWork();},
    compare:()=>{compare=!compare;drawWork();},
    orientation:value=>mesh?.view(value),
    zoom:value=>mesh?.zoom(Number(value)),
    conversation:()=>openConversation({kind:'work'}),
    'part-conversation':()=>{if(!selectedPart||!detail.selected.manifest[selectedPart])throw new Error('Select a current saved mesh part.');return openConversation({kind:'cad',path:selectedPart,part:selectedPart,hash:detail.selected.manifest[selectedPart].hash});},
    line:async(value,el)=>{const epoch=viewEpoch,artifact=artifactEpoch,path=file,stateId=el.dataset.side==='before'?compareState:detail.selected.state.id;const state=stateId===detail.selected.state.id?detail.selected:await api('get_development_state',{state_id:stateId});if(epoch!==viewEpoch||artifact!==artifactEpoch)return;return openConversation({kind:'code',path,hash:state.manifest[path].hash,line:Number(value)},stateId);},
    'close-conversation':closeConversation,
    'back-to-artifact':closeConversation,
    unmention:value=>{mentions=mentions.filter(x=>x!==value);drawConversation();},
    import:importFiles,share,'import-project':importProject,
    'load-updates':loadUpdates,
    latest:()=>{selectConversation(null);file='';const url='#'+view.workURL(detail.work.id);if(location.hash===url)return render();location.hash=url;},
    discussions:()=>modal('Conversations',view.discussionList(detail),null),
    'open-thread':id=>{const t=detail.discussion_index.find(t=>t.id===id);if(!t)return;$('#dialog').close();const url='#'+view.workURL(detail.work.id,t.state_id,t.id);if(location.hash===url)return render();location.hash=url;},
    changes:()=>modal('Changed files',`<p>Compared with the previous checkpoint.</p><div class="studio-share-files">${detail.selected.diffs.map(d=>`<div><span>${e(d.path)}</span><span>${e(d.kind)}</span></div>`).join('')||'<p>No file changes in this checkpoint.</p>'}</div>`,null),
    'download-file':async path=>download(path.split('/').pop(),await bytes(downloadState,path,32*1024*1024),'application/octet-stream'),
    'import-help':()=>modal('Connect / continue',view.connectionInstructions(detail,location.origin+location.pathname.replace(/\/$/,'')),null),
    details:()=>modal('Saved version',`<dl class="context-list"><dt>State</dt><dd>${e(detail.selected.state.id)}</dd><dt>Checkpoint note</dt><dd>${e(detail.selected.state.summary)}</dd><dt>Shared update notes</dt><dd>${e((detail.versions.find(v=>v.id===detail.selected.state.id)?.notes||[]).join(' · ')||'No note')}</dd><dt>Snapshot</dt><dd>${e(detail.selected.state.snapshot)}</dd><dt>Work</dt><dd>${e(detail.selected.status.work)}</dd><dt>Sharing</dt><dd>${e(detail.selected.status.sharing)}</dd><dt>Verification</dt><dd>${e(detail.selected.status.verification)}</dd><dt>Adoption</dt><dd>${e(detail.selected.status.adoption)}</dd><dt>Not captured</dt><dd>${e(detail.capture.missing.join(', ')||'No omissions declared')}</dd></dl><p>Restore this saved version into a new directory:</p><pre>gantry restore-development-state ${e(detail.selected.state.id)} --destination ./continued-work --key resume-unique-key</pre>${view.workspaceContext(detail.selected)}${view.link('session/'+detail.work.session_id,'Open execution and review tools')}`,null),
    component:value=>{const n=project.hierarchy.find(n=>n.id===value);if(!n)return;const works=relatedWorks(overview.works,project.id,value,project.hierarchy);document.querySelectorAll('.structure-card').forEach(el=>{el.classList.toggle('selected',el.dataset.value===value);el.setAttribute('aria-pressed',String(el.dataset.value===value));});const panel=document.querySelector('.structure-inspector');panel.hidden=false;document.querySelector('.structure-workspace').classList.add('with-inspector');$('#studio-component-detail').innerHTML=`<div class="studio-row"><strong>${e(n.title)}</strong>${view.link(view.projectURL(project.id,value,'work'),'View work →')}</div><div class="studio-small">${e((n.paths||[]).join(' · ')||'No saved files mapped')}</div>${view.workList(works)}`;layout.mount();},
    'close-component':()=>{document.querySelector('.structure-inspector').hidden=true;document.querySelector('.structure-workspace').classList.remove('with-inspector');document.querySelectorAll('.structure-card').forEach(el=>{el.classList.remove('selected');el.setAttribute('aria-pressed','false');});layout.mount();},
    'more-work':async cursor=>{const epoch=viewEpoch;const next=await api('studio_overview',{after:cursor});if(epoch!==viewEpoch)return;overview.works.push(...next.works);overview.next=next.next;const list=$('.studio-worklist');if(list)list.outerHTML=view.workList(relatedWorks(overview.works,project.id,node?.id,project.hierarchy));document.querySelector('[data-studio=more-work]')?.remove();if(next.next)$('#main').insertAdjacentHTML('beforeend',a('more-work','Load more work',next.next,'class="studio-more"'));},
    'more-inbox':async cursor=>{const epoch=viewEpoch;const next=await api('studio_inbox',{after:cursor});if(epoch!==viewEpoch)return;const wrapper=document.createElement('div');wrapper.innerHTML=view.inbox(next.items);$('.studio-worklist').insertAdjacentHTML('beforeend',wrapper.querySelector('.studio-worklist').innerHTML);document.querySelector('[data-studio=more-inbox]')?.remove();if(next.next)$('#main').insertAdjacentHTML('beforeend',a('more-inbox','Load more',next.next,'class="studio-more"'));},
    'new-work':async()=>{const epoch=viewEpoch,targetProject=project,targetNode=node;if(!targetProject.structure_state)throw new Error('Import a project state first from Projects & uploads.');const state=await api('get_development_state',{state_id:targetProject.structure_state});if(epoch!==viewEpoch)return;const session=await api('session_details',{session_id:state.state.session_id});if(epoch!==viewEpoch)return;modal('New work',`<label>Title<input name="title" required maxlength="240"></label><label>Purpose<textarea name="purpose" required></textarea></label><label>Assignee<select name="assignee">${[...new Set([session.session.owner,...session.session.actors])].map(id=>`<option>${e(id)}</option>`).join('')}</select></label><label>Target paths (one per line)<textarea name="scope" required>${e((targetNode?.paths||state.state.hierarchy.flatMap(n=>n.paths)).join('\n'))}</textarea></label>`,async form=>{const result=await api('begin_change',{state_id:state.state.id,title:form.title.value,purpose:form.purpose.value,assignee:form.assignee.value,write_scope:form.scope.value.split('\n').map(x=>x.trim()).filter(Boolean),dependencies:[]});location.hash=view.workURL(result.id);},'Start work');}
  };
  document.addEventListener('click',async event=>{const el=event.target.closest('[data-studio]');if(!el||!handles()||el.disabled)return;const fn=handlers[el.dataset.studio];if(!fn)return;event.preventDefault();el.disabled=true;try{await fn(el.dataset.value,el);}catch(err){fail(err);}finally{el.disabled=false;}});
  document.addEventListener('keydown',event=>{if(event.target.matches('.studio-node')&&['Enter',' '].includes(event.key)){event.preventDefault();handlers.component(event.target.dataset.value);}});
  document.addEventListener('input',event=>{if(event.target.id==='studio-draft'){draft=event.target.value;remember();}});
  document.addEventListener('change',event=>{const el=event.target;const run=async()=>{
    if(el.id==='studio-version'){selectConversation(null);threadDetail=null;file='';location.hash=view.workURL(detail.work.id,el.value);}
    if(el.id==='studio-compare-version'){compareState=el.value;drawWork();}
    if(el.id==='studio-file')chooseFile(el.value);
    if(el.id==='studio-mention'&&el.value){if(!mentions.includes(el.value))mentions.push(el.value);draft+=(draft&&!draft.endsWith(' ')?' ':'')+'@'+el.value+' ';remember();drawConversation();$('#studio-draft').focus();}
  };run().catch(fail);});
  document.addEventListener('submit',async event=>{if(event.target.id!=='studio-comment-form')return;event.preventDefault();const submit=event.submitter;submit.disabled=true;
    const epoch=viewEpoch,wid=detail.work.id,target={...conversation},body=draft;
    const sameTarget=()=>epoch===viewEpoch&&detail?.work.id===wid&&JSON.stringify(conversation)===JSON.stringify(target);
    const known=detail.participants.map(p=>p.id);const typed=known.filter(id=>body.split(/\s+/).some(word=>word==='@'+id));
    try{if(!body.trim())throw new Error('Write a comment first.');
      const result=await api('studio_comment',{work_id:wid,...target,body,mentions:[...new Set([...mentions,...typed])]});
      const key=JSON.stringify([wid,target]);if(drafts.get(key)?.draft===body)drafts.delete(key);
      if(!sameTarget())return;
      if(draft===body){draft='';mentions=[];}const fresh=await api('studio_work',{work_id:wid,state_id:target.state_id});
      if(!sameTarget())return;
      if(target.state_id===detail.selected.state.id)detail=fresh;else{threadDetail=fresh;detail={...detail,discussion_index:fresh.discussion_index,activity_token:fresh.activity_token};}
      activity.set('studio_work',{work_id:wid,activity_only:true},fresh);
      conversation.thread_id=result.thread_id;remember();await drawWork();toast('Comment saved');
    }catch(err){if(sameTarget()&&$('#studio-comment-error'))$('#studio-comment-error').textContent=err.message;else fail(err);}finally{submit.disabled=false;}
  });
  return {handles,render,reset,checkUpdates:()=>handles()&&!document.hidden?activity.check():undefined,leave:()=>{layout.leave();onboarding?.leave();crewSetup?.leave();activity.clear();remember();viewEpoch++;artifactEpoch++;disposeMesh();document.body.classList.remove('studio-mode');$('#main').className='';}};
}
