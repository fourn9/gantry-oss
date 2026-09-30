import {$,esc as e,short,badge,button as b,options,toast,download} from './ui.js';
import * as view from './views.js';
import * as reviewView from './review_views.js';

let token='', base='', data, identity, detail, projectDetail, dialogSubmit, revision=0, refreshing=false;
let reviewPage, reviewTeam, reviewDetail, reviewAutomation;
let inspector='Changes',selectedState='',lastSession='',automationStatus;
const filter={layout:'board',project:'',status:'',query:''};
// randomUUID is only exposed in secure contexts by some mobile browsers. The
// pilot can be opened over a private LAN HTTP address, so keep idempotency
// keys working there as well.
const key=()=>{
  if(globalThis.crypto?.randomUUID)return globalThis.crypto.randomUUID();
  if(globalThis.crypto?.getRandomValues){
    const bytes=new Uint8Array(16);globalThis.crypto.getRandomValues(bytes);
    bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
    const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  }
  return 'fallback-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
};
async function api(command,args={},idempotency=key()){
  const response=await fetch(base+'/v1/commands/'+command,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token,'Idempotency-Key':idempotency},body:JSON.stringify(args)});
  const value=await response.json();if(!response.ok||value.error)throw new Error((value.error?.message||'Request failed')+(value.error?.code?' ['+value.error.code+']':''));return value.result;
}
function fail(error){$('#error-banner').textContent=error.message||String(error);$('#error-banner').hidden=false;}
function route(){const [name='sessions',id]=location.hash.slice(1).split('/');return {name:name||'sessions',id};}
function modal(title,body,submit,label='Save'){$('#dialog-title').textContent=title;$('#dialog-body').innerHTML=body;$('#dialog-error').textContent='';$('#dialog-submit').textContent=label;$('#dialog-submit').hidden=!submit;dialogSubmit=submit;$('#dialog').showModal();}
function closeModal(){$('#dialog').close();dialogSubmit=null;}
const field=(label,name,value='',extra='')=>`<label>${e(label)}<input name="${e(name)}" value="${e(value)}" ${extra}></label>`;
const area=(label,name,value='',extra='')=>`<label>${e(label)}<textarea name="${e(name)}" ${extra}>${e(value)}</textarea></label>`;
const formData=form=>Object.fromEntries(new FormData(form));
const projectSelect=(selected='')=>`<label>Project<select name="project_id" required>${options(data.projects,'id','name',selected)}</select></label>`;
async function render(){
  if(!data)return;const r=route(),current=++revision;
  const side=view.sidebar(data,r.name);$('#nav').innerHTML=side.nav;$('#sidebar-projects').innerHTML=side.projects;$('#recent-sessions').innerHTML=side.recent;
  if(r.name==='session'){
    if(lastSession!==r.id){selectedState='';inspector='Changes';lastSession=r.id;}
    const [value,team]=await Promise.all([api('session_details',{session_id:r.id,...(selectedState?{state_id:selectedState}:{})}),api('get_review_team',{session_id:r.id})]);if(current!==revision)return;detail={...value,review_team:team.team};
    $('#breadcrumb').innerHTML=`<a href="#sessions">Sessions</a><span class="muted">/</span><span>${e(detail.session.title)}</span>`;
    $('#main').innerHTML=view.session(data,detail,inspector,location.origin+base);
    $('#note-form').onsubmit=async event=>{event.preventDefault();const submit=event.submitter;submit.disabled=true;try{await api('add_session_note',{session_id:r.id,body:$('#note-body').value});toast('Context saved');await refresh();}catch(err){fail(err);}finally{submit.disabled=false;}};
  }else if(r.name==='reviews'||r.name==='review'){
    const record=r.name==='review'?await api('get_change_review',{submission_id:r.id}):null;
    const sid=record?.session_id||r.id;
    const [session,page,team,automation]=await Promise.all([api('session_details',{session_id:sid}),api('list_change_reviews',{session_id:sid,limit:100}),api('get_review_team',{session_id:sid}),api('review_automation_status',{session_id:sid})]);
    if(current!==revision)return;detail=session;reviewPage=page;reviewTeam=team.team;reviewDetail=record;reviewAutomation=automation;
    $('#breadcrumb').innerHTML=`<a href="#session/${e(sid)}">${e(session.session.title)}</a><span>/</span><span>Change reviews</span>`;
    $('#main').innerHTML=(record?reviewView.review(record,session):reviewView.reviews(session,page,reviewTeam))+reviewView.automation(automation);
  }else if(r.name==='automation'){
    const value=await api('automation_status');if(current!==revision)return;automationStatus=value;
    $('#breadcrumb').textContent='Automation';$('#main').innerHTML=view.automation(data,value);
  }else if(r.name==='project'){
    const value=await api('project_details',{project_id:r.id});if(current!==revision)return;projectDetail=value;
    $('#breadcrumb').innerHTML=`<a href="#projects">Projects</a><span class="muted">/</span><span>${e(value.project.name)}</span>`;$('#main').innerHTML=view.project(data,value);
  }else{
    const name=['sessions','inbox','projects','integrations'].includes(r.name)?r.name:'sessions';
    $('#breadcrumb').textContent={sessions:'Sessions',inbox:'Incoming',projects:'Projects',integrations:'Integrations'}[name];
    $('#main').innerHTML=name==='sessions'?view.sessions(data,filter):view[name](data);
  }
  $('#project-filter')?.addEventListener('change',event=>{filter.project=event.target.value;render().catch(fail);});
  $('#status-filter')?.addEventListener('change',event=>{filter.status=event.target.value;render().catch(fail);});
  $('#session-search')?.addEventListener('input',event=>{filter.query=event.target.value;const pos=event.target.selectionStart;render().then(()=>{$('#session-search')?.focus();$('#session-search')?.setSelectionRange(pos,pos);}).catch(fail);});
  $('#state-select')?.addEventListener('change',event=>{selectedState=event.target.value;render().catch(fail);});
}
async function refresh(){if(!token||refreshing)return;refreshing=true;try{data=await api('product_overview');await render();$('#refresh-status').textContent='Updated just now';$('#connection-status').textContent='Connected';$('#error-banner').hidden=true;}catch(err){$('#connection-status').textContent='Connection needs attention';fail(err);}finally{refreshing=false;}}
async function projectForm(id){const p=data.projects.find(x=>x.id===id);modal(p?'Edit project':'Create project',field('Project name','name',p?.name||'','required maxlength="120" placeholder="e.g. Robot fleet"')+area('Description','description',p?.description||'','required maxlength="4000" placeholder="Robot, fleet and improvement scope"'),async form=>{const f=formData(form);await api('save_project',{...f,...(p?{project_id:p.id,version:p.version}:{})});toast('Project saved');});}
async function newSession(pid='',signalId=''){
  if(!data.projects.length)return projectForm();
  const source=data.signals.find(s=>s.id===signalId);pid=source?.project_id||pid||data.projects[0].id;
  const pd=await api('project_details',{project_id:pid});
  const bundles=pd.uploads.map(u=>({id:u.snapshot,name:u.summary+' · '+u.file_count+' files'}));
  const starts=(pd.project.baseline_state?[{id:'baseline',name:'Shared baseline · '+short(pd.project.baseline_state)}]:[]).concat(bundles);
  modal('New improvement session',projectSelect(pid)+field('Session title','title',source?.title||'','required maxlength="240" placeholder="e.g. Investigate intermittent head stalls"')+area('Goal & acceptance conditions','goal','','required placeholder="What should improve? Which conditions must hold?"')+`<label>Starting state<select name="start" required><option value="">Select a saved baseline or upload</option>${options(starts)}</select></label><p>Starts in suggestions-only mode. Execution requires explicit scope, trusted recipes and a budget.</p>${source?'<p class="notice">Linked source: '+e(source.title)+'</p>':''}${!starts.length?'<p class="notice warning">Upload a starting bundle from the project first.</p>':''}`,async form=>{
    const f=formData(form);if(f.project_id!==pid)throw new Error('Close this dialog and start from the selected project to load its baseline.');const start=f.start;delete f.start;
    const result=await api('create_product_session',{...f,...(signalId?{signal_id:signalId}:{}),...(start==='baseline'?{state_id:pd.project.baseline_state}:{snapshot:start})});location.hash='session/'+result.session.id;toast('Session created. Waiting for Mentor.');
  },'Create session');
  $('[name=project_id]',$('#dialog')).onchange=event=>{const next=event.target.value;closeModal();newSession(next,signalId).catch(fail);};
}
async function upload(pid,sid){if(!pid)throw new Error('Link this session to a project first.');modal('Upload saved files',`<p>Save editable sources and the assets needed to continue. Files are retained as immutable artifacts; uploading does not adopt a design.</p>${field('Bundle description','summary','','required placeholder="e.g. CAD, controller and failure logs"')}<label>Category<select name="category">${['cad','electrical','code','simulation','logs','other'].map(x=>`<option>${x}</option>`).join('')}</select></label><label>Files<input name="files" type="file" multiple required></label><p class="caption">32 MiB per file · 48 MiB per batch. Credentials are not accepted. Use the local adapter for directory capture and larger bundles.</p>`,async form=>{
    const files=[...$('[name=files]',form).files];if(files.length>200||files.reduce((n,f)=>n+f.size,0)>48*1024*1024)throw new Error('Upload limit: 200 files, 48 MiB per batch.');const values={};
    for(const f of files){if(f.size>32*1024*1024)throw new Error(f.name+' exceeds 32 MiB.');if(values[f.name])throw new Error('Duplicate filename: '+f.name);values[f.name]=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(f);});}
    await api('upload_project_files',{project_id:pid,...(sid?{session_id:sid}:{}),summary:form.summary.value,category:form.category.value,files:values});toast('Files saved. Current development state is unchanged.');
  },'Upload');}
async function integrationForm(id='',provider='github'){
  if(!data.projects.length)return projectForm();const i=data.integrations.find(x=>x.id===id);provider=i?.provider||provider;
  const workspace=$('#workspace').value.trim().toUpperCase().replaceAll('-','_');const example='GANTRY_CONNECTOR_'+(workspace?workspace+'_':'')+'GITHUB';
  modal(i?'Configure connection':'Connect '+(provider==='github'?'GitHub':'Monitoring API'),projectSelect(i?.project_id)+`<input type="hidden" name="provider" value="${e(provider)}">`+field('Connection name','name',i?.name||(provider==='github'?'GitHub':'Operational monitoring'),'required')+(provider==='github'?field('Repository','repository',i?.repository||'','required placeholder="owner/repository"')+field('Server credential reference (private repositories)','credential_ref',i?.credential_ref||'',`placeholder="${example}"`)+`<p class="caption">The operator sets this environment variable on the cloud server. Do not paste a token here. Leave blank for public repositories.</p>`:`<p>Send authenticated POST requests to <code>/v1/commands/ingest_signal</code>. Use a scoped service identity with read + record permissions.</p>${i?`<pre>${e(JSON.stringify({integration_id:i.id,source_event_id:'unique-event-id',title:'Head stalled',body:'Operational observation',occurred_at:'2026-09-22T12:00:00Z',observed_configuration:{hardware:'unknown',software:'unknown'}},null,2))}</pre>`:''}`)+`<label class="check-label"><input type="checkbox" name="enabled" ${!i||i.enabled?'checked':''}> Enable connection</label>`,async form=>{
    const f=formData(form);f.enabled=form.enabled.checked;if(!f.credential_ref)delete f.credential_ref;const saved=await api('configure_integration',{...f,...(i?{integration_id:i.id,version:i.version}:{})});toast(saved.enabled?'Connection configured. Synchronize to verify access.':'Connection disconnected. Existing evidence retained.');
  },'Save connection');
  if(i){$('[name=project_id]',$('#dialog')).disabled=true;const el=$('[name=repository]',$('#dialog'));if(el)el.readOnly=true;const submit=dialogSubmit;dialogSubmit=form=>{const project=$('[name=project_id]',form);project.disabled=false;return submit(form);};}
}
async function sessionSettings(){const d=detail.session,l=detail.link;modal('Session settings',`<p>Suggestions, execution permission and formal adoption are separate.</p><label>Mode<select name="mode">${options([{id:'record',name:'Record only'},{id:'suggest',name:'Suggestions only'},{id:'execute',name:'Delegated execution'}],'id','name',d.mode)}</select></label>${field('Participants (comma separated IDs)','actors',d.actors.join(', '),'required')}${area('Allowed write paths (one per line)','scope',d.write_scope.join('\n'))}${area('Trusted recipes (JSON name → SHA-256)','recipes',JSON.stringify(d.recipes,null,2))}<div class="form-row">${field('Maximum executions','max',d.max_executions,'type="number" min="0" required')}${field('Timeout (seconds)','timeout',d.timeout_seconds,'type="number" min="1" max="7200" required')}</div>${field('Reason','reason','','required')}${l.id?`<label>Session outcome<select name="outcome">${options(['open','paused','closed'].map(id=>({id,name:id})),'id','name',l.outcome)}</select></label>`:''}`,async form=>{
    const f=formData(form);const recipes=JSON.parse(f.recipes);await api('configure_development',{session_id:d.id,version:d.version,reason:f.reason,mode:f.mode,actors:f.actors.split(',').map(x=>x.trim()).filter(Boolean),write_scope:f.scope.split('\n').map(x=>x.trim()).filter(Boolean),recipes,max_executions:Number(f.max),timeout_seconds:Number(f.timeout),max_parallel:d.max_parallel});
    if(l.id&&f.outcome!==l.outcome)await api('set_session_outcome',{session_id:d.id,version:l.version,outcome:f.outcome,reason:f.reason});toast('Delegation updated');
  });}
async function browseUpload(id){const u=projectDetail.uploads.find(x=>x.id===id),info=await api('restore_artifact',{revision_id:u.snapshot,metadata_only:true});modal(u.summary,Object.entries(info.manifest.files).map(([path,f])=>`<div class="file-row"><span class="name">${e(path)}<div class="caption">${f.size} bytes · ${e(short(f.hash))}</div></span><button type="button" data-action="download-upload" data-id="${e(path)}" data-snapshot="${e(u.snapshot)}">Download</button></div>`).join(''),null);}
async function downloadFile(snapshot,path){const value=await api('restore_artifact',{revision_id:snapshot,metadata_only:true});const info=value.manifest.files[path];const pieces=[];for(let i=0;i<(info.chunks?.length||1);i++){const part=await api('read_artifact_chunk',{revision_id:snapshot,path,index:i});const raw=Uint8Array.from(atob(part.content),c=>c.charCodeAt(0));const actual=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(x=>x.toString(16).padStart(2,'0')).join('');if(actual!==part.hash)throw new Error('Download integrity check failed.');pieces.push(raw);}const file=new Blob(pieces);const actual=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))].map(x=>x.toString(16).padStart(2,'0')).join('');if(actual!==info.hash)throw new Error('Whole-file integrity check failed.');download(path.split('/').pop(),file,'application/octet-stream');}
async function adoption(stateId){const v=detail.state;modal('Review for formal adoption',`<p>State <code>${e(short(stateId))}</code></p><div class="status-axes">${badge(v.status.verification)}${badge(v.status.adoption)}</div><p>Unfinished: ${e(v.state.unfinished.join('; ')||'None submitted')}</p><p>Not captured: ${e(v.state.capture.missing.join('; ')||'No declared omissions')}</p>${area('Reason, evidence and remaining conditions','reason','','required')}<p class="notice">This creates a review proposal. It does not adopt or deploy anything.</p>`,async form=>{const p=await api('propose_state_adoption',{state_id:stateId,reason:form.reason.value});await api('submit',{proposal_id:p.id,version:p.version});setTimeout(()=>reviewProposal(p.id),0);toast('Review proposal created');},'Create review proposal');}
async function reviewProposal(pid){const ctx=await api('review_context',{proposal_id:pid});const p=ctx.proposal;modal('Human adoption review',`<p>${e(p.title)}</p><pre>${e(JSON.stringify(ctx.diff||p.changes,null,2))}</pre>${area('Review reason','reason','','required')}<p class="notice">Approval is bound to candidate version ${p.version}. Owner review and formal commit are checked by Core.</p>`,async form=>{const args={proposal_id:p.id,version:p.version,reason:form.reason.value};await api('endorse',args);await api('review_adoption',{...args,verdict:'approve'});await api('commit',args);toast('Formal adoption recorded. Nothing was deployed.');},'Approve & adopt');}

const lines=value=>value.split('\n').map(x=>x.trim()).filter(Boolean);
async function configureReviewTeam(){
  const current=reviewTeam;
  const value=current?{session_id:detail.session.id,version:current.version,coordinator:current.coordinator,required_roles:current.required_roles,members:current.members}:{session_id:detail.session.id,version:0,coordinator:'coordinator',required_roles:[],members:[{principal_id:identity.id,role:'developer',side:'user'},{principal_id:'',role:'coordinator',side:'gantry'}]};
  modal('Review delegation',`<p>Use existing session participants. Customer developers and Gantry Mentor must have separate identities. Changing delegation makes existing reviews stale.</p>${area('Team JSON','team',JSON.stringify(value,null,2),'required rows="18" spellcheck="false"')}`,async form=>{const input=JSON.parse(form.team.value);if(input.session_id!==detail.session.id)throw new Error('Session cannot change.');await api('configure_review_team',input);toast('Review team saved');});
}
async function submitPR(changeId=''){
  const changes=detail.states.changes;
  if(!changes.length)throw new Error('Create a change set from a saved state before submitting.');
  modal('Submit change for review',`<p>Submits the current immutable head of this change. The assignee must submit using their own identity.</p><label>Change<select name="change" required>${options(changes,'id','title',changeId)}</select></label><label>Design stage<select name="stage">${options(['concept','preliminary','detailed','integration'].map(id=>({id,name:id})))}</select></label>${area('Review question','question','','required')}${area('Acceptance conditions (one per line)','acceptance','','required')}${area('Additional required specialist roles (one per line)','roles',reviewTeam?.required_roles.join('\n')||'')}<p class="caption">Required team reports cannot be skipped. Submission does not authorize execution or adoption.</p>`,async form=>{const change=changes.find(c=>c.id===form.change.value);const result=await api('submit_change_review',{change_id:change.id,version:change.version,question:form.question.value,stage:form.stage.value,acceptance:lines(form.acceptance.value),required_roles:lines(form.roles.value)});location.hash='review/'+result.id;toast('PR submitted');},'Submit PR');
}
async function reviewResponse(){const r=reviewDetail;modal('Attach corrected candidate',`${field('Saved candidate state ID','state','','required')}${field('Execution ID (optional)','execution')}${area('Finding responses (JSON)','responses',JSON.stringify(r.output.findings.map(f=>({finding_id:f.id,explanation:''})),null,2),'required rows="12"')}<p>Core checks that this is the current descendant state of the same change. Attaching a candidate does not resubmit or approve it.</p>`,async form=>{await api('respond_to_change_review',{submission_id:r.id,candidate_state:form.state.value,responses:JSON.parse(form.responses.value),...(form.execution.value?{execution_id:form.execution.value}:{})});toast('Corrected candidate attached. Resubmit the change to request review.');});}
async function reviewAutomationConfig(){const p=reviewAutomation.policy;modal('PR automation',`<p>A connected customer-side worker uses the configured identities. Enabling this queue does not start a paid API or prove that a worker is online.</p><label class="check-label"><input type="checkbox" name="enabled" ${p?.enabled?'checked':''}> Enable review and revision jobs</label>${field('Developer principal','developer',p?.developer_principal||'','required')}${field('Maximum revision rounds','rounds',p?.max_rounds||3,'type="number" min="1" max="10" required')}${field('Maximum jobs','jobs',p?.max_jobs||20,'type="number" min="1" max="100" required')}`,async form=>{await api('configure_review_automation',{session_id:detail.session.id,version:p?.version||0,enabled:form.enabled.checked,developer_principal:form.developer.value,max_rounds:Number(form.rounds.value),max_jobs:Number(form.jobs.value)});toast('PR automation policy saved');});}

const automationFields=['project_id','version','enabled','analysts','provider','session_template','max_daily_calls','max_daily_microusd','max_monthly_microusd','max_active_sessions','max_sessions_per_day','max_replans_per_session','max_daily_executions','cooldown_seconds','max_attempts_per_trigger','reason'];
function policyInput(p){return Object.fromEntries(automationFields.map(k=>[k,p[k]]));}
async function automationConfig(pid){
  const current=automationStatus.projects.find(x=>x.project.id===pid)?.policy;
  const value=current?policyInput(current):{project_id:pid,version:0,enabled:false,analysts:[identity.id],
    provider:{kind:'disabled',model:'not-configured',max_input_tokens:100000,max_output_tokens:4000,timeout_seconds:60,input_microusd_per_million:0,output_microusd_per_million:0},
    session_template:{mode:'suggest',actors:[identity.id],write_scope:[],recipes:{},max_executions:0,timeout_seconds:300,max_parallel:1},
    max_daily_calls:20,max_daily_microusd:0,max_monthly_microusd:0,max_active_sessions:3,max_sessions_per_day:3,max_replans_per_session:5,max_daily_executions:0,cooldown_seconds:30,max_attempts_per_trigger:3,reason:'Configure project automation'};
  modal('Automation delegation',`<p>Set delegated agent IDs, provider, budgets and trusted recipe hashes. Amounts are in micro-USD (1,000,000 = $1). Credentials belong in the worker environment.</p><p class="notice">Enabling authorizes automatic session creation. Execution follows the session template; formal adoption always requires a human. Saving changed delegation cancels running automated jobs.</p>${area('Policy JSON','policy',JSON.stringify(value,null,2),'required rows="22" spellcheck="false"')}`,async form=>{
    const input=JSON.parse(form.policy.value);if(input.project_id!==pid)throw new Error('Project cannot change.');
    await api('configure_automation',input);toast('Automation delegation saved');});
}
const actions={
  'change-reviews':()=>{location.hash='reviews/'+detail.session.id;},
  'review-team':configureReviewTeam,'submit-pr':submitPR,'review-response':reviewResponse,
  'review-context':()=>download('review-context.json',JSON.stringify(reviewDetail,null,2)),
  'review-automation':reviewAutomationConfig,
  'reviews-more':async cursor=>{const next=await api('list_change_reviews',{session_id:detail.session.id,after:cursor,limit:100});reviewPage={items:[...reviewPage.items,...next.items],next_cursor:next.next_cursor};$('#main').innerHTML=reviewView.reviews(detail,reviewPage,reviewTeam)+reviewView.automation(reviewAutomation);},
  'automation-config':automationConfig,
  'automation-pause':async id=>{const p=automationStatus.projects.find(x=>x.project.id===id).policy;await api('configure_automation',{...policyInput(p),enabled:false,reason:'Paused by project operator'});toast('Automation paused');await refresh();},
  'analysis-record':id=>{const run=automationStatus.projects.flatMap(p=>p.runs).find(r=>r.id===id);modal('Analysis record',`<pre>${e(JSON.stringify(run,null,2))}</pre>`,null);},
  'new-project':()=>projectForm(),'edit-project':id=>projectForm(id),'new-session':id=>newSession(id),
  'board':()=>{filter.layout='board';return render();},'list':()=>{filter.layout='list';return render();},
  'from-source':id=>newSession('',id),'source':async id=>modal('Source evidence',view.sourceDetails(await api('get_signal',{signal_id:id})),null),
  'upload':id=>upload(id),'session-upload':()=>upload(detail.link.project_id,detail.session.id),'upload-files':browseUpload,
  'download-upload':(id,el)=>downloadFile(el.dataset.snapshot,id),'download-file':id=>downloadFile(detail.state.state.snapshot,id),
  'download-context':()=>download('gantry-context.json',JSON.stringify(detail.state,null,2)),
  'connect':()=>integrationForm(),'connect-github':()=>integrationForm(),'connect-monitoring':()=>integrationForm('','monitoring'),'integration-config':id=>integrationForm(id),
  'sync':async id=>{const result=await api('sync_integration',{integration_id:id});if(!result.synced)throw new Error(result.error.message);toast('GitHub synchronized: '+result.signal_ids.length+' issues / PRs');await refresh();},
  'inspect':name=>{inspector=name;return render();},'session-settings':sessionSettings,
  'request-mentor':()=>modal('Request Mentor',area('What should Mentor investigate?','summary','','required placeholder="Use the saved state and source evidence to propose the next bounded task."')+'<p>Saved to the queue. A configured Mentor worker must be online to generate a proposal.</p>',async form=>{await api('request_mentor',{session_id:detail.session.id,summary:form.summary.value});toast('Mentor request saved');},'Request proposal'),
  'check-contract':async id=>{const r=await api('check_execution',{contract_id:id});modal('Execution conditions',r.allowed?'<p>Current checks pass. The local runner rechecks atomically before launch.</p>':`<p>Execution held</p><ul>${r.reasons.map(x=>`<li>${e(x.replaceAll('_',' '))}</li>`).join('')}</ul>`,null);},
  'execution-json':id=>download('execution.json',JSON.stringify(detail.executions.find(x=>x.id===id),null,2)),
  'execution-logs':async id=>{const x=detail.executions.find(x=>x.id===id);const info=await api('restore_artifact',{revision_id:x.logs_snapshot,metadata_only:true});modal('Execution logs',Object.keys(info.manifest.files).map(path=>`<div class="file-row"><span class="name">${e(path)}</span><button type="button" data-action="download-upload" data-id="${e(path)}" data-snapshot="${e(x.logs_snapshot)}">Download</button></div>`).join(''),null);},
  'contract-json':id=>download('work-contract.json',JSON.stringify(detail.contracts.find(c=>c.id===id),null,2)),
  'baseline':async id=>{const p=data.projects.find(p=>p.id===id);const states=data.sessions.filter(s=>s.project_id===id&&s.active_state).map(s=>({id:s.active_state,name:s.title+' · '+short(s.active_state)}));modal('Select project baseline',`<p>This selects a continuation point, not an adopted release or observed fleet configuration.</p><label>State<select name="state" required>${options(states,'id','name',p.baseline_state)}</select></label>`,async form=>{await api('save_project',{project_id:p.id,version:p.version,name:p.name,description:p.description,baseline_state:form.state.value});toast('Project baseline selected');});},
  'adopt-state':adoption,
  'adapter-help':()=>modal('Connect a local workspace',`<p>Install Gantry on the customer PC. Requests are outbound HTTPS; CAD and simulation stay on that PC.</p><pre>gantry --url ${e(location.origin+base)} --token-file ./access.token capture-workspace --root ./robot-project --key initial-upload</pre><p>Use checkpoint-workspace after edits and restore-development-state on another machine. Only saved files are acquired; unsaved CAD operations and missing dependencies stay explicit.</p>`,null),
  'worker-help':()=>modal('Cloud Mentor · local runner',`<p>The cloud Mentor proposes structured work. A local runner retrieves permitted contracts and uploads steps, outputs and failures.</p><pre>gantry --url ${e(location.origin+base)} --token-file ./agent.token product-worker --kind runner --config ./runner.json --journal ./gantry-journal --iterations 20</pre><p>The workspace administrator provisions an agent identity and adds it to the session. Configure allowed recipes, input state, write scope and execution budget before enabling execution.</p><p class="notice">No arbitrary shell commands are accepted from issues or uploaded files. A configured Mentor provider is required; this installation does not silently invoke a paid model.</p>`,null)
};
document.addEventListener('click',async event=>{const el=event.target.closest('[data-action]');if(!el||!token)return;event.preventDefault();const fn=actions[el.dataset.action];if(!fn)return;el.disabled=true;try{await fn(el.dataset.id,el);}catch(err){fail(err);}finally{el.disabled=false;}});
$('#dialog-form').onsubmit=async event=>{event.preventDefault();const submit=dialogSubmit;if(!submit)return;$('#dialog-submit').disabled=true;try{await submit(event.target);closeModal();await refresh();}catch(err){$('#dialog-error').textContent=err.message;}finally{$('#dialog-submit').disabled=false;}};
$('#dialog-close').onclick=closeModal;$('#dialog-cancel').onclick=closeModal;
$('#workspace').value=location.pathname.match(/^\/w\/([^/]+)/)?.[1]||'';
$('#login-form').onsubmit=async event=>{event.preventDefault();const workspace=$('#workspace').value.trim();if(workspace&&!/^[a-z0-9][a-z0-9-]{0,47}$/.test(workspace)){$('#login-error').textContent='Invalid workspace ID';return;}event.submitter.disabled=true;try{token=$('#token-file').files[0]?(await $('#token-file').files[0].text()).trim():$('#token').value.trim();base=workspace?'/w/'+workspace:'';identity=await api('identity');$('#token').value='';$('#token-file').value='';$('#login').hidden=true;$('#shell').hidden=false;$('#workspace-name').textContent=workspace||'Local';$('#actor-name').textContent=identity.id||identity.actor_id||'Member';$('#actor-avatar').textContent=$('#actor-name').textContent[0].toUpperCase();await refresh();}catch(err){token='';$('#login-error').textContent=err.message;}finally{event.submitter.disabled=false;}};
$('#logout').onclick=()=>{token='';data=null;detail=null;revision++;closeModal();$('#main').replaceChildren();$('#login').hidden=false;$('#shell').hidden=true;$('#login-error').textContent='';};
$('#refresh').onclick=refresh;$('#new-session').onclick=()=>newSession().catch(fail);
$('#menu-button').onclick=()=>{const open=$('.sidebar').classList.toggle('open');$('#menu-button').setAttribute('aria-expanded',String(open));};
window.addEventListener('hashchange',()=>{$('.sidebar').classList.remove('open');$('#menu-button').setAttribute('aria-expanded','false');render().catch(fail);});
setInterval(()=>{if(token&&!document.hidden&&!$('#dialog').open&&!['TEXTAREA','INPUT','SELECT'].includes(document.activeElement?.tagName))refresh();},15000);
