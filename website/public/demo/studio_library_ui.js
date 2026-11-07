import {$,esc as e,short,download} from './ui.js?v=library-20261107';
import * as view from './studio_views.js?v=library-20261107';
import * as library from './studio_library_views.js?v=library-20261107';
import {libraryURL,meshFile,lineDiff,linesOf,participantName} from './studio_model.js?v=library-20261107';
import {parseMesh,mountMesh} from './studio_mesh.js?v=library-20261107';
import {createActivityMonitor} from './studio_activity.js?v=library-20261107';

export function mergeThreads(old,latest){
  const by=new Map(old.map(t=>[t.id,t]));
  for(const t of latest){const messages=new Map((by.get(t.id)?.messages||[]).map(m=>[m.id,m]));for(const m of t.messages)messages.set(m.id,m);by.set(t.id,{...t,messages:[...messages.values()]});}
  return [...by.values()];
}

// Presentation of one saved state. No synthetic work records or mixed branch heads.
export function createLibraryUI({api,modal,toast,fail,bytes,layout}){
  let active=false,ready=false,epoch=0,previewEpoch=0,project,node,section,state,list,anchor,data,panel='',mesh,compare=false,previous,selection,draft='',mentions=[],historyPage;
  const drafts=new Map(),a=library.action;
  const activity=createActivityMonitor({api,notice:text=>{const el=$('#studio-live-notice');if(el){el.hidden=!text;el.querySelector('span').textContent=text;}}});
  const target=()=>({project_id:project.id,state_id:state.id,anchor});
  const draftKey=()=>state&&JSON.stringify([project.id,state.id,anchor]);
  function remember(){if(ready&&state&&anchor)drafts.set(draftKey(),{draft,mentions:[...mentions]});}
  function dispose(){mesh?.destroy();mesh=null;}
  function leave(){remember();activity.clear();active=false;ready=false;epoch++;previewEpoch++;dispose();}
  function reset(){leave();drafts.clear();}
  const alive=n=>active&&n===epoch;
  function go(value=anchor,tab=section,sid=state.id,thread=''){
    location.hash=libraryURL(project.id,node?.id,tab,sid,value,thread);
  }
  function detail(){return {...data,work:{project_id:project.id,session_id:state.session_id,title:project.name,
    version:data.session_version,head:state.id,write_scope:data.write_scope},selected:{state}};}
  async function render(p,n,parts){
    leave();active=true;const generation=++epoch,tab=parts[3];
    let loaded=await api('studio_library',{project_id:p.id,...(parts[4]?{state_id:parts[4]}:{}),section:tab,...(n?{component_id:n.id}:{})});
    if(!alive(generation))return;const st=loaded.state;
    const chosen=parts[5]?JSON.parse(parts[5]):tab==='requirements'&&loaded.items[0]?{kind:'requirement',requirement_id:loaded.items[0].requirement_id,revision_id:loaded.items[0].revision_id}:loaded.items[0]?{kind:'file',path:loaded.items[0].path,hash:loaded.items[0].hash}:n?{kind:'component',component_id:n.id}:{kind:'project'};
    if(tab==='files'&&chosen.path&&!loaded.items.some(f=>f.path===chosen.path)){
      const exact=await api('studio_library',{project_id:p.id,state_id:st.id,section:'files',path:chosen.path});if(!alive(generation))return;
      loaded={...loaded,selected_file:exact.items[0]};
    }
    const related=await api('studio_related',{project_id:p.id,state_id:st.id,anchor:chosen});if(!alive(generation))return;
    project=p;node=n;section=tab;list=loaded;state=st;anchor=chosen;data=related;ready=true;panel=parts[6]?'discussion':'';compare=false;previous=null;
    activity.set('studio_related',target(),data);
    $('#breadcrumb').innerHTML=view.projectHeader(project,node,section,state.id);
    selection={anchor,state_id:state.id,...(parts[6]&&parts[6]!=='selection'?{thread_id:parts[6]}:{})};
    const saved=drafts.get(draftKey());draft=saved?.draft||'';mentions=saved?.mentions||[];
    await draw(generation);
    if(parts[7]&&data.can_comment&&alive(generation))api('studio_acknowledge',{notification_id:parts[7]}).catch(fail);
  }
  function controls(){return `<div class="library-toolbar"><div><strong>${e(state.summary)}</strong><small title="${e(state.id)}">${e(short(state.id))} · ${e(state.sharing)} · ${state.adoption==='human_adopted'?'Formally adopted':'Not formally adopted'}</small></div><div class="studio-actions">${a('context','Shared context')}${a('history','Versions')}${a('restore','Restore / continue')}</div></div>`;}
  async function draw(generation=epoch){
    const attempt=++previewEpoch;dispose();$('#main').innerHTML=`${controls()}<div class="library-body ${panel?'library-panel-open':''}"><aside class="library-browser" aria-label="${section==='files'?'Saved files':'Requirements'}">${section==='files'?library.fileList(list,anchor.path):library.requirementList(list,anchor.requirement_id)}</aside><section class="library-content"><div class="library-selectionbar"><span title="${e(library.anchorTitle(anchor))}">${e(library.anchorTitle(anchor))}</span><div class="studio-actions">${anchor.path?a('download','Download'):''}${anchor.path&&state.parents?.length?a('compare','Compare to parent','',`aria-pressed="${compare}"`):''}${a('related','Related','',`aria-pressed="${panel==='related'}"`)}${a('discussion','Discuss','',`aria-pressed="${panel==='discussion'}"`)}</div></div><div id="library-preview" class="library-preview" tabindex="-1">${view.hint('Loading saved content…')}</div></section>${panel?'<aside class="library-panel" aria-label="Related information and conversation" tabindex="-1"><div id="library-panel-content"></div></aside>':''}</div>`;
    drawPanel();layout.mount();
    try{await preview(generation,attempt);}catch(err){if(alive(generation)&&attempt===previewEpoch&&$('#library-preview'))$('#library-preview').innerHTML=view.hint('Preview unavailable',err.message);}
  }
  function drawPanel(){const el=$('#library-panel-content');if(!el)return;
    el.innerHTML=`<div class="library-panel-tabs">${a('related','Related','',`aria-pressed="${panel==='related'}"`)}${a('discussion','Discussion','',`aria-pressed="${panel==='discussion'}"`)}${a('close','×','','aria-label="Close panel"')}</div>`+(panel==='related'?library.related(data,project.id):view.conversation(detail(),selection,draft,mentions)+'<p class="studio-small library-demo-note">Mentions stay in this tab. Ask and Assign require a connected workspace; no Crew agent runs here.</p>'+(data.message_next?a('more-messages','Load earlier messages',data.message_next):''));
  }
  function fileInfo(){return list.items.find(f=>f.path===anchor.path)||list.selected_file||data.files.find(f=>f.path===anchor.path);}
  function wrapper(info,st=state){return {state:st,manifest:{[info.path]:info}};}
  async function preview(generation,attempt){
    const current=()=>alive(generation)&&attempt===previewEpoch;
    const el=$('#library-preview');
    if(anchor.kind==='requirement'){const r=data.requirements.find(x=>x.requirement_id===anchor.requirement_id);el.innerHTML=r?library.requirementDetail(r):view.hint('Requirement not linked');return;}
    if(!anchor.path){el.innerHTML=view.hint(anchor.kind==='component'?(node?.title||anchor.component_id):project.name,'Select a file to inspect its saved content, or open Related and Discussion.');return;}
    const info=fileInfo();if(!info||info.hash!==anchor.hash)throw new Error('This target is not present in the saved state.');
    if(compare&&!previous){const result=await api('studio_library',{project_id:project.id,state_id:state.parents[0],section:'files',path:anchor.path});if(!current())return;previous=result;}
    const before=compare?previous?.items[0]:null;
    const footer=`<div class="studio-caption"><span>${e(compare?short(previous.state.id)+' → '+short(state.id):short(state.id))} · ${e(short(info.hash))}</span><span>${e(info.size)} bytes</span></div>`;
    if(meshFile(anchor.path)){
      const triangles=parseMesh(await bytes(wrapper(info),info.path),info.path),meshes=[{path:info.path,triangles}];
      if(before)meshes.push({path:info.path,previous:true,triangles:parseMesh(await bytes(wrapper(before,previous.state),before.path),before.path)});
      if(!current())return;
      el.innerHTML=`<div class="studio-mesh-tools">${a('orientation','Isometric','iso')}${a('orientation','Front','front')}${a('orientation','Top','top')}${a('part','Discuss part')}</div><div class="studio-cad"><canvas id="library-canvas" tabindex="0" aria-label="Saved mesh preview"></canvas></div>${footer}<p class="studio-small">Saved mesh · Coordinates and units as exported${before?' · Amber: parent geometry':''}</p>`;
      mesh=mountMesh($('#library-canvas'),meshes,()=>openPart());return;
    }
    if(/\.(sldprt|sldasm|catpart|catproduct|prt|asm|step|stp|iges|igs|f3d|3dm|pdf|zip|png|jpg|jpeg|gif|stl|obj)$/i.test(info.path)){el.innerHTML=view.hint('Saved source','This format has no in-browser preview. Download the original or restore this state to your external tool.')+footer;return;}
    let text,beforeText='';
    try{text=new TextDecoder('utf-8',{fatal:true}).decode(await bytes(wrapper(info),info.path,262144));if(before)beforeText=new TextDecoder('utf-8',{fatal:true}).decode(await bytes(wrapper(before,previous.state),before.path,262144));if(text.includes('\0')||beforeText.includes('\0'))throw new Error('binary');}
    catch(err){if(!current())return;el.innerHTML=view.hint('Text preview unavailable','Binary, unsupported encoding, or more than 256 KiB. Download or restore the original file.')+footer;return;}
    if(!current())return;
    const rows=compare?lineDiff(beforeText,text):linesOf(text).map((text,i)=>({text,after:i+1,kind:'same'}));
    el.innerHTML=(compare&&!before?'<p class="studio-small">File not present in the parent state.</p>':'')+`<div class="studio-code">${rows?rows.slice(0,4000).map(r=>`<button class="studio-code-line ${r.kind} ${anchor.line===r.after?'selected':''}" data-library="line" data-value="${r.after||r.before}" data-side="${r.after?'after':'before'}"><span>${r.before||''}</span><span>${r.after||''}</span><span>${r.kind==='add'?'+':r.kind==='remove'?'−':' '}</span><code>${e(r.text)||' '}</code></button>`).join(''):view.hint('Comparison too large','Download both saved versions to compare in your editor.')}</div>${footer}${rows?.length>4000?'<p>First 4,000 lines shown. Download the full saved file.</p>':''}`;
  }
  async function refresh(){const generation=epoch;remember();const fresh=await api('studio_related',target());if(!alive(generation))return;data={...fresh,threads:mergeThreads(data.threads,fresh.threads)};activity.set('studio_related',target(),data);await draw(epoch);}
  function openPart(){go({kind:'cad',path:anchor.path,part:anchor.path,hash:anchor.hash},'files',state.id,'selection');}
  // "selection" requests opening the panel, not a persisted thread ID.
  function discussion(){panel='discussion';selection={anchor,state_id:state.id};draw(epoch);}
  async function showHistory(after){const generation=epoch;const page=await api('studio_library',{project_id:project.id,state_id:state.id,section:'versions',...(after?{after}:{})});if(!alive(generation))return;historyPage=after?{...page,items:[...historyPage.items,...page.items]}:page;modal('Saved states',library.history(historyPage,project.id,section,node?.id),null);}
  async function moreRelated(cursor){const generation=epoch;const fresh=await api('studio_related',{...target(),after:cursor});if(!alive(generation))return;data={...data,works:[...data.works,...fresh.works],next:fresh.next};drawPanel();}
  const handlers={
    file:path=>{const f=list.items.find(f=>f.path===path);go({kind:'file',path,hash:f.hash});},
    requirement:id=>{const r=list.items.find(r=>r.requirement_id===id);go({kind:'requirement',requirement_id:id,revision_id:r.revision_id});},
    related:()=>{panel='related';draw(epoch);},discussion,close:()=>{panel='';draw(epoch);},
    compare:()=>{compare=!compare;draw(epoch);},orientation:v=>mesh?.view(v),part:openPart,
    line:(line,button)=>{const old=button.dataset.side==='before';go({kind:'code',path:anchor.path,hash:old?previous.items[0].hash:anchor.hash,line:Number(line)},'files',old?previous.state.id:state.id,'selection');},
    download:async()=>{const f=fileInfo();download(f.path.split('/').pop(),await bytes(wrapper(f),f.path,32*1024*1024),'application/octet-stream');},
    history:()=>showHistory(),'more-history':showHistory,
    'select-state':sid=>{$('#dialog').close();go(null,section,sid);},
    more:async cursor=>{const generation=epoch;const page=await api('studio_library',{project_id:project.id,state_id:state.id,section,...(node?{component_id:node.id}:{}),after:cursor});if(!alive(generation))return;list={...list,items:[...list.items,...page.items],next:page.next};draw(epoch);},
    'more-related':moreRelated,
    'more-messages':async cursor=>{const generation=epoch;const fresh=await api('studio_related',{...target(),message_after:cursor});if(!alive(generation))return;data={...data,message_next:fresh.message_next,threads:mergeThreads(data.threads,fresh.threads)};drawPanel();},
    context:async()=>{const context=await api('studio_context',target()),m=context.mandatory;modal('Shared saved context',`<p>People and Crew agents retrieve these same saved requirements, constraints and open questions. This sample performs no model call.</p><dl class="context-list"><dt>State</dt><dd>${e(context.source.state_id)}</dd><dt>Requirements</dt><dd>${m.requirements.map(r=>`<p>${e(r.description)} · ${e(r.revision_id)}</p>`).join('')}</dd>${[['Constraints',m.constraints],['Open questions',m.open_questions],['Unfinished',m.unfinished],['Not captured',m.capture.missing]].map(([label,items])=>`<dt>${label}</dt><dd><ul>${items.map(x=>`<li>${e(x)}</li>`).join('')}</ul></dd>`).join('')}</dl><p class="studio-small">File bodies are retrieved separately by saved snapshot, path and hash.</p>`,null);},
    restore:()=>modal('Restore / continue',`<p>In a connected workspace, restore the exact saved state into a new local directory:</p><pre>gantry restore-development-state ${e(state.id)} --destination ./continued-project --key UNIQUE_KEY</pre><p class="studio-small">This invented demo state exists only in this tab; this command is an example, not a usable restore target. Use a real state with your existing Gantry connection and credential. Restoring files does not run CAD tools, reproduce unsaved external state, or formally adopt a design.</p><dl class="context-list"><dt>Snapshot</dt><dd>${e(state.snapshot)}</dd><dt>Capture</dt><dd><pre>${e(JSON.stringify(state.capture,null,2))}</pre></dd><dt>Unfinished</dt><dd>${e(state.unfinished.join(' · ')||'No unfinished items declared')}</dd></dl>`,null)
  };
  document.addEventListener('click',async ev=>{
    if(!active||!ready)return;const b=ev.target.closest('[data-library],[data-studio]');if(!b||b.disabled)return;
    let fn=b.dataset.library?handlers[b.dataset.library]:null;
    if(b.dataset.studio==='load-updates')fn=refresh;
    if(['close-conversation','back-to-artifact'].includes(b.dataset.studio))fn=handlers.close;
    if(b.dataset.studio==='unmention')fn=id=>{mentions=mentions.filter(x=>x!==id);remember();drawPanel();};
    if(!fn)return;ev.preventDefault();b.disabled=true;try{await fn(b.dataset.value,b);}catch(err){fail(err);}finally{b.disabled=false;}
  });
  document.addEventListener('input',ev=>{if(active&&ready&&ev.target.id==='studio-draft'){draft=ev.target.value;remember();}});
  document.addEventListener('change',ev=>{if(!active||!ready||ev.target.id!=='studio-mention'||!ev.target.value)return;const id=ev.target.value;if(!mentions.includes(id))mentions.push(id);draft+=(draft?' ':'')+'@'+participantName(data.participants,id)+' ';remember();drawPanel();$('#studio-draft')?.focus();});
  document.addEventListener('submit',async ev=>{
    if(!active||!ready||ev.target.id!=='studio-comment-form')return;ev.preventDefault();const generation=epoch,b=ev.submitter,body=draft,t={...target()},key=draftKey();b.disabled=true;
    try{if(!body.trim())throw new Error('Write a comment first.');const message=await api('studio_comment',{...t,body,mentions,...(selection.thread_id?{thread_id:selection.thread_id}:{})});
      if(drafts.get(key)?.draft===body)drafts.delete(key);if(!alive(generation))return;if(draft===body){draft='';mentions=[];}selection.thread_id=message.thread_id;await refresh();toast('Comment saved');
    }catch(err){if(alive(generation)&&$('#studio-comment-error'))$('#studio-comment-error').textContent=err.message;else fail(err);}finally{b.disabled=false;}
  });
  return {render,leave,reset,checkUpdates:()=>active&&ready?activity.check():undefined,get active(){return active;}};
}
