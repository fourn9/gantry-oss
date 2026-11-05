import {$,esc as e,short,icon,download} from './ui.js';
import {requestContext,componentScope} from './studio_context.js?v=evidence-20261105';
import * as view from './studio_views.js?v=evidence-20261105';
import {cadFile,meshFile,codeFile,versionLabel,fileChanges,lineDiff,linesOf,relatedWorks,commentCount} from './studio_model.js?v=evidence-20261105';
import {parseMesh,mountMesh} from './studio_mesh.js';
import {createActivityMonitor} from './studio_activity.js';

export function createStudio({api,modal,toast,fail}){
  let overview,detail,project,node,viewEpoch=0,artifactEpoch=0,mesh,tab='cad',compare=false,compareState='',file='',selectedPart='',conversation=null,lastWork='',draft='',mentions=[],threadDetail,evidenceFocus=null;
  let downloadState=null,recent=[],cache=new Map(),drafts=new Map(),cameras=new Map(),meshKey='';
  const route=()=>location.hash.slice(1).split('/').map(x=>decodeURIComponent(x));
  const handles=()=>['studio','studio-work','studio-inbox','studio-recent'].includes(route()[0]||'studio');
  const a=view.action;
  const activity=createActivityMonitor({api,notice:text=>{const el=$('#studio-live-notice');if(el){el.hidden=!text;el.querySelector('span').textContent=text;}}});
  function reset(){activity.clear();viewEpoch++;artifactEpoch++;disposeMesh();cache.clear();drafts.clear();cameras.clear();overview=detail=undefined;recent=[];lastWork='';evidenceFocus=null;conversation=null;threadDetail=null;draft='';mentions=[];}
  function disposeMesh(){if(mesh){if(mesh.camera)cameras.set(meshKey,mesh.camera());mesh.destroy();mesh=null;while(cameras.size>50)cameras.delete(cameras.keys().next().value);}}
  function chooseFile(path){evidenceFocus=null;file=path;selectedPart=path;selectConversation(null);threadDetail=null;drawWork();}
  function remember(){if(conversation)drafts.set(JSON.stringify([detail.work.id,conversation]),{draft,mentions:[...mentions]});}
  function selectConversation(value){remember();conversation=value;const saved=drafts.get(JSON.stringify([detail.work.id,value]));draft=saved?.draft||'';mentions=saved?.mentions||[];}
  function sidebar(){const side=view.sidebar(overview,recent,{project:project?.id});$('#nav').innerHTML=side.nav;$('#sidebar-projects').innerHTML=side.projects;$('#recent-sessions').innerHTML=side.recent;}
  async function render(){
    remember();activity.clear();const current=++viewEpoch,parts=route(),kind=parts[0]||'studio';artifactEpoch++;disposeMesh();
    document.body.classList.add('studio-mode');$('#main').className='studio-main';
    $('#main').innerHTML=view.hint('Loading workspace…');
    const loaded=await api('studio_overview');if(current!==viewEpoch||!handles())return;overview=loaded;activity.set('studio_overview',{},loaded);
    if(kind==='studio-work'){
      const value=await api('studio_work',{work_id:parts[1],...(parts[2]?{state_id:parts[2]}:{})});if(current!==viewEpoch||!handles())return;
      if(lastWork!==value.work.id){conversation=null;threadDetail=null;draft='';mentions=[];tab='cad';compare=false;file='';selectedPart='';lastWork=value.work.id;evidenceFocus=null;}
      detail=value;activity.set('studio_work',{work_id:value.work.id,activity_only:true},value);project=overview.projects.find(p=>p.id===detail.work.project_id);node=null;
      recent=[detail.work,...recent.filter(w=>w.id!==detail.work.id)].slice(0,30);
      const context=requestContext(value,parts[3]);
      const showThread=Boolean(context);
      if(parts[3]){selectConversation(null);threadDetail=null;}
      if(context){tab=context.tab;file=context.file;selectedPart=context.part;compare=context.compare;compareState=context.compareState;evidenceFocus=context.conversation;selectConversation(context.conversation);}

      sidebar();$('#breadcrumb').innerHTML=project?view.projectHeader(project,null,'work'):'Work';
      await drawWork();if(current!==viewEpoch)return;if(showThread&&globalThis.innerWidth>1024)focusConversation();
      if(parts[4]&&detail.can_comment)api('studio_acknowledge',{notification_id:parts[4]}).catch(fail);
      return;
    }
    project=overview.projects.find(p=>p.id===parts[1])||overview.projects[0];node=project?.hierarchy.find(n=>n.id===parts[2]);sidebar();
    if(kind==='studio-inbox'){
      const inbox=await api('studio_inbox');if(current!==viewEpoch)return;activity.set('studio_inbox',{},inbox);$('#breadcrumb').textContent='Inbox';$('#main').innerHTML=view.inbox(inbox.items)+(inbox.next?a('more-inbox','Load more',inbox.next,'class="studio-more"'):'');return;
    }
    if(kind==='studio-recent'){$('#breadcrumb').textContent='Recent';$('#main').innerHTML='<div class="studio-page-title"><h1>Recent</h1><span class="studio-small">Work opened in this tab</span></div>'+view.workList(recent,'No recently opened work.');return;}
    if(!project){$('#breadcrumb').textContent='Projects';$('#main').innerHTML=view.hint('Start a shared project','Create a project, import saved files, then start work.')+'<div class="studio-empty"><button data-action="new-project">Create project</button></div>';return;}
    const projectTab=parts[3]==='work'?'work':'structure';$('#breadcrumb').innerHTML=view.projectHeader(project,node,projectTab);
    $('#main').innerHTML=(projectTab==='structure'?view.structure(project,node,overview.works):
      '<div class="studio-list-tools">'+a('new-work','New work')+'</div>'+view.projectWork(project,overview.works,node,overview.collaboration))+
      (overview.next?a('more-work','Load more work',overview.next,'class="studio-more"'):'');
  }
  function drawWork(){
    disposeMesh();
    const versions=detail.versions,index=versions.findIndex(v=>v.id===detail.selected.state.id);
    if(!versions.some(v=>v.id===compareState&&v.id!==detail.selected.state.id))compareState=versions[Math.max(0,index-1)]?.id;
    if(index===0)compare=false;
    $('#main').innerHTML=view.workDetail(detail,{tab,compare,compareState,conversation});
    drawConversation();const epoch=viewEpoch;const load=loadArtifact();const request=artifactEpoch;return load.catch(error=>{if(epoch===viewEpoch&&request===artifactEpoch&&$('#studio-artifact'))$('#studio-artifact').innerHTML=view.hint('Unable to load artifact',error.message);});
  }
  function drawConversation(){if(conversation&&$('#studio-conversation')){const panel=$('#studio-conversation');panel.innerHTML=view.conversation(threadDetail||detail,conversation,draft,mentions);const messages=panel.querySelector('.studio-messages');messages.scrollTop=messages.scrollHeight;}}
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
    if(!paths.includes(file)){const changed=new Set(v.diffs.map(d=>d.path));const scoped=path=>detail.work.components.some(c=>c.paths?.some(p=>path===p||(p.endsWith('/')&&path.startsWith(p))));file=paths.find(p=>changed.has(p)&&(tab!=='cad'||meshFile(p)))||paths.find(p=>scoped(p)&&(tab!=='cad'||meshFile(p)))||paths.find(meshFile)||paths[0];}
    target.innerHTML=`<div class="studio-filebar"><select id="studio-file" aria-label="Artifact file">${options(paths,file)}</select></div><div id="studio-file-content" aria-live="polite">${view.hint('Loading saved version…')}</div>`;
    const body=$('#studio-file-content');
    downloadState=v.manifest[file]?v:old;
    if(tab==='cad'){
      if(!meshFile(file)){body.innerHTML=view.hint('Preview not supported for this format','The native source is saved. Export an STL or OBJ preview from your CAD tool and import it alongside the editable file.')+a('download-file','Download saved source',file)+a('import-help','Connect a CAD adapter');return;}
      const currentPaths=Object.keys(v.manifest).filter(meshFile);const previewPaths=currentPaths.length<=12?currentPaths:[file].filter(p=>v.manifest[p]);
      const meshes=[];let triangles=0;
      for(const p of previewPaths){const t=parseMesh(await bytes(v,p),p);triangles+=t.length;if(triangles>80000)throw new Error('Assembly preview is too large. Export a lighter mesh.');meshes.push({path:p,triangles:t});}
      if(old?.manifest[file])meshes.push({path:file,previous:true,triangles:parseMesh(await bytes(old,file),file)});
      if(current!==artifactEpoch)return;
      target.querySelector('.studio-filebar').insertAdjacentHTML('beforeend',`<div class="studio-mesh-tools"><div>${a('orientation','Isometric','iso')}${a('orientation','Top','top')}${a('orientation','Front','front')}${a('zoom','−','0.8','aria-label="Zoom out"')}${a('zoom','+','1.25','aria-label="Zoom in"')}</div></div>`);
      body.innerHTML=`<div class="studio-cad"><canvas id="studio-canvas" aria-label="Saved 3D mesh preview" tabindex="0"></canvas></div><div class="studio-caption"><span>${e(compare?'Current assembly · Amber: previous '+file:'Saved mesh preview · Coordinates and units as exported')}</span>${a('part-conversation',icon('sessions')+'Discuss this part'+(commentCount(detail,v.state.id,file)?' · '+commentCount(detail,v.state.id,file):''),'',!v.manifest[file]?'disabled':'')}</div>${!v.manifest[file]?'<p class="studio-small">This file was deleted in the selected version. Amber geometry is from the previous version.</p>':''}`;
      selectedPart=previewPaths.includes(file)?file:'';
      meshKey=detail.work.id+':'+v.state.id;mesh=mountMesh($('#studio-canvas'),meshes,chooseFile,cameras.get(meshKey),Object.fromEntries(previewPaths.map(p=>[p,commentCount(detail,v.state.id,p)])));mesh.select(selectedPart);return;
    }
    const read=async(st,p)=>st?.manifest[p]?new TextDecoder('utf-8',{fatal:true}).decode(await bytes(st,p,262144)):'';
    const text=await read(v,file),before=await read(old,file);if(current!==artifactEpoch)return;
    if(text.includes('\0')||before.includes('\0'))throw new Error('This file is binary. Use the external editor.');
    const rows=compare?lineDiff(before,text):linesOf(text).map((t,i)=>({text:t,after:i+1,kind:'same'}));
    const line=(r,side)=>`<button class="studio-code-line ${r.kind}" data-studio="line" data-value="${r.after||r.before}" data-side="${side||(!r.after?'before':'after')}"><span>${r.before||''}</span><span>${r.after||''}</span><span>${r.kind==='add'?'+':r.kind==='remove'?'−':' '}</span><code>${e(r.text)||' '}</code>${commentCount(detail,r.after?v.state.id:old?.state.id,file,r.after||r.before)?`<span class="studio-line-comments" title="Comments on this line">${icon('sessions')}${commentCount(detail,r.after?v.state.id:old?.state.id,file,r.after||r.before)}</span>`:''}</button>`;
    body.innerHTML=`<div class="studio-code-source studio-small">${e(detail.source?.repository||'Repository not recorded')}${detail.source?.commit?' · Source commit '+e(short(detail.source.commit)):''}</div><div class="studio-code" aria-label="Code and line comments">${rows?rows.slice(0,4000).map(r=>line(r)).join(''):`<p class="studio-small">Large comparison: separate versions</p><h2>Before</h2>${linesOf(before).slice(0,2000).map((text,i)=>line({text,before:i+1,kind:'remove'},'before')).join('')}<h2>After</h2>${linesOf(text).slice(0,2000).map((text,i)=>line({text,after:i+1,kind:'add'},'after')).join('')}`}</div><div class="studio-caption"><span>${compare?e(versionLabel(detail.versions.find(x=>x.id===old.state.id)))+' → ':''}${e(versionLabel(detail.versions.find(x=>x.id===v.state.id)))} · ${e(file)}</span><span>Select a line to discuss</span></div>${(rows?.length>4000||!rows)?'<p class="studio-small">Preview is limited; restore files to inspect the complete change.</p>':''}`;
    const focus=conversation||evidenceFocus;
    if(focus?.anchor.kind==='code'&&focus.anchor.path===file&&[v.state.id,old?.state.id].includes(focus.state_id)){const side=focus.state_id===v.state.id?'after':'before';const row=body.querySelector(`[data-studio=line][data-side=${side}][data-value="${focus.anchor.line}"]`);row?.classList.add('selected');row?.setAttribute('aria-current','true');row?.scrollIntoView({block:'nearest'});}
  }
  async function openConversation(anchor,stateId=detail.selected.state.id){
    const epoch=viewEpoch,artifact=artifactEpoch,wid=detail.work.id;
    const older=stateId===detail.selected.state.id?null:await api('studio_work',{work_id:wid,state_id:stateId});
    if(epoch!==viewEpoch||artifact!==artifactEpoch||detail.work.id!==wid||!handles())return;
    threadDetail=older;const source=threadDetail||detail;
    const t=source.threads.find(t=>JSON.stringify(Object.entries(t.anchor).sort())===JSON.stringify(Object.entries(anchor).sort()));
    evidenceFocus={anchor,state_id:stateId};selectConversation({anchor,state_id:stateId,...(t?{thread_id:t.id}:{})});await drawWork();if(epoch!==viewEpoch)return;focusConversation();
  }
  function focusConversation(){const panel=$('#studio-conversation');if(!panel)return;if(globalThis.innerWidth<=1024)panel.scrollIntoView({block:'start'});panel.focus({preventScroll:true});const messages=panel.querySelector('.studio-messages');if(messages)messages.scrollTop=messages.scrollHeight;}
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
    const captured=detail;
    modal('Import a sample update',`<p>In a connected workspace, you import changes saved in your CAD tool or editor.</p><p>For this demo, load a prepared edit within this work’s file scope. It stays in this tab and starts as an unshared, untested checkpoint.</p>`,async()=>{
      const result=await api('demo_import_update',{work_id:captured.work.id,version:captured.work.version});file='';toast('Sample edit loaded · Not yet shared');location.hash=view.workURL(captured.work.id,result.state.id);
    },'Load sample edit');
  }
  const handlers={
    'request-step':async value=>{
      const request=detail.demo_request;if(!request)return;
      if(value==='reply'){const context=requestContext(detail,request.thread_id);if(!context)return;tab=context.tab;file=context.file;selectedPart=context.part;compare=context.compare;compareState=context.compareState;await openConversation(request.anchor,request.state_id);$('#studio-draft')?.focus({preventScroll:globalThis.innerWidth>1024});return;}
      remember();selectConversation(null);threadDetail=null;tab=value;compare=value!=='checks';file='';compareState=detail.versions[0].id;
      await drawWork();$('#studio-artifact')?.scrollIntoView({block:'start'});
    },
    tab:async value=>{remember();selectConversation(null);threadDetail=null;tab=value;file='';evidenceFocus=null;
      const context=requestContext(detail,detail.demo_request?.thread_id);
      if(context&&value===context.tab){file=context.file;compare=context.compare;compareState=context.compareState;evidenceFocus=context.conversation;}
      else if(context?.related_anchor&&value===context.related_anchor.kind){file=context.related_anchor.path;selectedPart=context.related_anchor.part||'';compare=context.compare;compareState=context.compareState;evidenceFocus={anchor:context.related_anchor,state_id:context.conversation.state_id};}
      await drawWork();},
    compare:()=>{compare=!compare;drawWork();},
    orientation:value=>mesh?.view(value),
    zoom:value=>mesh?.zoom(Number(value)),
    conversation:()=>{$('#dialog').close();return openConversation({kind:'work'});},
    'part-conversation':()=>{if(!selectedPart||!detail.selected.manifest[selectedPart])throw new Error('Select a current saved mesh part.');return openConversation({kind:'cad',path:selectedPart,part:selectedPart,hash:detail.selected.manifest[selectedPart].hash});},
    line:async(value,el)=>{const epoch=viewEpoch,artifact=artifactEpoch,path=file,stateId=el.dataset.side==='before'?compareState:detail.selected.state.id;const state=stateId===detail.selected.state.id?detail.selected:await api('get_development_state',{state_id:stateId});if(epoch!==viewEpoch||artifact!==artifactEpoch)return;return openConversation({kind:'code',path,hash:state.manifest[path].hash,line:Number(value)},stateId);},
    'close-conversation':closeConversation,
    'back-to-artifact':closeConversation,
    unmention:value=>{mentions=mentions.filter(x=>x!==value);drawConversation();},
    import:importFiles,share,
    'load-updates':loadUpdates,
    latest:()=>{selectConversation(null);file='';const url='#'+view.workURL(detail.work.id);if(location.hash===url)return render();location.hash=url;},
    discussions:()=>modal('Conversations',view.discussionList(detail),null),
    'open-thread':id=>{const t=detail.discussion_index.find(t=>t.id===id);if(!t)return;$('#dialog').close();const url='#'+view.workURL(detail.work.id,t.state_id,t.id);if(location.hash===url)return render();location.hash=url;},
    changes:()=>modal('Changed files',`<p>Compared with the previous checkpoint.</p><div class="studio-share-files">${detail.selected.diffs.map(d=>`<div><span>${e(d.path)}</span><span>${e(d.kind)}</span></div>`).join('')||'<p>No file changes in this checkpoint.</p>'}</div>`,null),
    'download-file':async path=>download(path.split('/').pop(),await bytes(downloadState,path,32*1024*1024),'application/octet-stream'),
    'import-help':()=>modal('About this demo','<p>Explore sample geometry, compare versions, and discuss a part or code line. Import changes loads a prepared sample edit. Share update makes it shared within this tab.</p><p>No live tools, agents, model calls, uploads, or teammates are connected. Comments and edits are held only in memory; reset or reload clears them.</p><p>Use Gantry locally to connect your own workspace and tools.</p><p><a href="https://github.com/fourn9/gantry-oss" target="_blank" rel="noopener noreferrer">Get Gantry on GitHub ↗</a></p>',null),
    details:()=>modal('Saved version',`<dl class="context-list"><dt>State</dt><dd>${e(detail.selected.state.id)}</dd><dt>Checkpoint note</dt><dd>${e(detail.selected.state.summary)}</dd><dt>Shared update notes</dt><dd>${e((detail.versions.find(v=>v.id===detail.selected.state.id)?.notes||[]).join(' · ')||'No note')}</dd><dt>Snapshot</dt><dd>${e(detail.selected.state.snapshot)}</dd><dt>Work</dt><dd>${e(detail.selected.status.work)}</dd><dt>Sharing</dt><dd>${e(detail.selected.status.sharing)}</dd><dt>Verification</dt><dd>${e(detail.selected.status.verification)}</dd><dt>Adoption</dt><dd>${e(detail.selected.status.adoption)}</dd><dt>Not captured</dt><dd>${e(detail.capture.missing.join(', ')||'No omissions declared')}</dd></dl><p>This is an illustrative version in a browser-only demo. In a connected workspace, saved artifacts can be restored through the local adapter.</p>`,null),
    component:value=>{document.querySelectorAll('[data-studio=component]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.value===value)));const n=project.hierarchy.find(n=>n.id===value);const works=relatedWorks(overview.works,project.id,value,project.hierarchy);$('#studio-component-detail').innerHTML=`<div class="studio-row"><strong>${e(n.title)}</strong>${view.link(view.projectURL(project.id,value,'work'),'View work →')}</div><div class="studio-small">${e(n.paths.join(' · ')||'No saved files mapped')}</div>${view.workList(works)}`;$('#studio-component-detail').scrollIntoView({block:'nearest',behavior:'smooth'});},
    'more-work':async cursor=>{const epoch=viewEpoch;const next=await api('studio_overview',{after:cursor});if(epoch!==viewEpoch)return;overview.works.push(...next.works);overview.next=next.next;const list=$('.studio-worklist');if(list)list.outerHTML=view.workList(relatedWorks(overview.works,project.id,node?.id,project.hierarchy));document.querySelector('[data-studio=more-work]')?.remove();if(next.next)$('#main').insertAdjacentHTML('beforeend',a('more-work','Load more work',next.next,'class="studio-more"'));},
    'more-inbox':async cursor=>{const epoch=viewEpoch;const next=await api('studio_inbox',{after:cursor});if(epoch!==viewEpoch)return;const wrapper=document.createElement('div');wrapper.innerHTML=view.inbox(next.items);$('.studio-worklist').insertAdjacentHTML('beforeend',wrapper.querySelector('.studio-worklist').innerHTML);document.querySelector('[data-studio=more-inbox]')?.remove();if(next.next)$('#main').insertAdjacentHTML('beforeend',a('more-inbox','Load more',next.next,'class="studio-more"'));},
    'new-work':async()=>{
      const epoch=viewEpoch,targetProject=project,targetNode=node;
      if(!targetProject.structure_state)throw new Error('Import a project state first.');
      const state=await api('get_development_state',{state_id:targetProject.structure_state});if(epoch!==viewEpoch)return;
      const session=await api('session_details',{session_id:state.state.session_id});if(epoch!==viewEpoch)return;
      const nodes=state.state.hierarchy;
      const label=n=>{const names=[n.title];let parent=nodes.find(x=>x.id===n.parent);const seen=new Set([n.id]);while(parent&&!seen.has(parent.id)){seen.add(parent.id);names.unshift(parent.title);parent=nodes.find(x=>x.id===parent.parent);}return names.join(' / ');};
      modal('New work',`<label>Title<input name="title" required maxlength="240" placeholder="What are you working on?"></label><label>Component<select name="component" required><option value="">Choose a component</option>${nodes.map(n=>`<option value="${e(n.id)}" ${targetNode?.id===n.id?'selected':''}>${e(label(n))}</option>`).join('')}</select></label><label>Assignee<select name="assignee">${[...new Set([session.session.owner,...session.session.actors])].map(id=>`<option>${e(id)}</option>`).join('')}</select></label><label>Goal<textarea name="purpose" required maxlength="1000" placeholder="What should be different when this is done?"></textarea></label><details class="studio-scope-details"><summary>Advanced · Limit files</summary><label>Paths (optional, one per line)<textarea name="scope" placeholder="Leave empty to use the component’s mapped files"></textarea></label><p class="caption">Overrides can narrow the selected component’s scope.</p></details>`,async form=>{
        const scope=componentScope(nodes,form.component.value,form.scope.value);
        const result=await api('begin_change',{state_id:state.state.id,title:form.title.value,purpose:form.purpose.value,assignee:form.assignee.value,component_id:form.component.value,write_scope:scope,dependencies:[]});
        location.hash=view.workURL(result.id);
      },'Start work');
    }

  };
  document.addEventListener('click',async event=>{const el=event.target.closest('[data-studio]');if(!el||!handles()||el.disabled)return;const fn=handlers[el.dataset.studio];if(!fn)return;event.preventDefault();el.disabled=true;try{await fn(el.dataset.value,el);}catch(err){fail(err);}finally{el.disabled=false;}});
  document.addEventListener('keydown',event=>{if(event.target.matches('.studio-node')&&['Enter',' '].includes(event.key)){event.preventDefault();handlers.component(event.target.dataset.value);}});
  document.addEventListener('input',event=>{if(event.target.id==='studio-draft'){draft=event.target.value;remember();}});
  document.addEventListener('change',event=>{const el=event.target;const run=async()=>{
    if(el.id==='studio-version'){evidenceFocus=null;selectConversation(null);threadDetail=null;file='';location.hash=view.workURL(detail.work.id,el.value);}
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
  return {handles,render,reset,checkUpdates:()=>handles()&&!document.hidden?activity.check():undefined,leave:()=>{activity.clear();remember();viewEpoch++;artifactEpoch++;disposeMesh();document.body.classList.remove('studio-mode');$('#main').className='';}};
}
