import {$} from './ui.js';
import {intentKey} from './intent_key.js';
import * as views from './crew_setup_views.js';
import {sourceSelection,sourceSummary,encodeSources,agentPrompt,canStartWork,setupURL,activeJob,readyPreparation,editRole} from './crew_setup_model.js';
export function createCrewSetup({api,toast,fail}){
 let data,session,team,control={hosts:[],jobs:[],prepared:null},items=[],epoch=0,active=false,busy=false,dirty=false,timer=null;
 const intents=new Map(),current=v=>active&&epoch===v;
 const error=err=>{const el=$('#crew-error');if(el)el.textContent=err.message;else fail(err);};
 const show=()=>{const display={...control,jobs:control.jobs.map(j=>({...j,needs_stop_reconciliation:j.action==='start'&&j.status==='held'&&j.session_version!==session?.version}))};$('#main').innerHTML=views.review(data,team?.principals||[],display,team);dirty=false;};
 function pausePoll(){if(timer)clearTimeout(timer);timer=null;}
 function schedule(v){
  pausePoll();if(!current(v)||!activeJob(control)||activeJob(control).status==='held')return;
  timer=setTimeout(async()=>{if(!current(v))return;if(busy||dirty||document.visibilityState==='hidden'){schedule(v);return;}
   try{await refresh(v);if(current(v))show();}catch(err){if(current(v))error(err);}finally{if(current(v))schedule(v);}
  },2500);timer.unref?.();
 }
 async function mutate(name,args){const signature=JSON.stringify([name,args]);if(!intents.has(signature))intents.set(signature,intentKey());const result=await api(name,args,intents.get(signature));intents.delete(signature);return result;}
 async function loadSession(sid,v){
  const details=await api('session_details',{session_id:sid});if(!current(v))return;
  const projectId=details.link?.project_id;if(!projectId)throw new Error('Link this session to a Studio project before setting up the team.');
  const project=await api('studio_team',{project_id:projectId});if(!current(v))return;
  session=details.session;team=project.sessions.find(s=>s.id===sid);return team;
 }
 async function refresh(v){
  const saved=await api('get_crew_setup',{setup_id:data.id});if(!current(v))return;
  const controls=saved.can_confirm?await api('get_crew_setup_control',{setup_id:saved.id}):{hosts:[],jobs:[],prepared:null};if(!current(v))return;
  await loadSession(saved.session_id,v);if(current(v)){data=saved;control=controls;}
 }
 async function render(sid,id){
  pausePoll();const v=++epoch;active=true;busy=false;dirty=false;intents.clear();items=[];data=null;control={hosts:[],jobs:[],prepared:null};$('#breadcrumb').textContent='Team setup';
  $('#main').innerHTML='<div class="studio-empty" role="status">Loading team setup…</div>';
  try{
   if(id){const result=await api('get_crew_setup',{setup_id:id});if(!current(v))return;if(result.session_id!==sid)throw new Error('This setup belongs to a different project session.');data=result;
    await loadSession(sid,v);if(!current(v))return;control=data.can_confirm?await api('get_crew_setup_control',{setup_id:id}):control;if(current(v)){show();schedule(v);}}
   else{const row=await loadSession(sid,v);if(!current(v))return;const drafts=await api('list_crew_setups',{session_id:sid});if(current(v))$('#main').innerHTML=views.start(session,drafts,row?.project?.organization_id?{id:row.project.organization_id,name:row.project.organization_name||''}:null);}
  }catch(err){if(current(v)){$('#main').innerHTML='<section class="onboarding"><h1>Unable to load team setup</h1><p id="crew-error" role="alert"></p><a href="#studio">Back to workspace</a></section>';error(err);}}
 }
 const hostFor=(form,prepared=false)=>{
  const id=prepared?control.prepared?.host_id:(form?.elements?.host_id?.value||$('#crew-host')?.value);
  const h=control.hosts.find(x=>x.id===id);if(!h?.online)throw new Error('Connect your customer runtime, then refresh.');return h;
 };
 const jobArgs=(action,host)=>({setup_id:data.id,version:data.version,host_id:host.id,config_hash:host.config_hash,action});
 function assertOwner(){if(!data.can_confirm)throw new Error('Only the project owner can make this change.');if(activeJob(control))throw new Error('Wait for the current operation, or retry its saved journal if held.');}
 function editing(el){
  const form=el.closest?.('.crew-role-edit,#crew-correct');if(!form)return;dirty=true;
  // One role at a time: switching editors must not discard unsaved values.
  document.querySelectorAll?.('.crew-role-edit,#crew-correct').forEach(other=>{if(other!==form)other.querySelectorAll('input,textarea,select,button').forEach(x=>x.disabled=true);});
 }
 document.addEventListener('input',event=>{if(active)editing(event.target);});
 document.addEventListener('change',event=>{
  if(!active||busy)return;const el=event.target;
  if(el.name==='crew_sources'&&el.closest('#crew-start')){items=sourceSelection(el.files);$('#crew-source-preview').innerHTML=views.sources(items);}
  if(el.dataset.crewFile!==undefined){const item=items[Number(el.dataset.crewFile)];if(item&&!item.excluded)item.selected=el.checked;const s=sourceSummary(items);$('#crew-source-preview strong').textContent=`${s.count} exports · ${(s.size/1024/1024).toFixed(2)} MiB selected`;}
  if(el.dataset.crewProvider!==undefined){const item=items[Number(el.dataset.crewProvider)];if(item)item.provider=el.value;}
  editing(el);
 });
 document.addEventListener('click',async event=>{
  const el=event.target.closest('[data-crew]');if(!active||busy||!el||el.disabled)return;event.preventDefault();const v=epoch;busy=true;el.disabled=true;pausePoll();
  try{
   const action=el.dataset.crew;
   if(action==='copy-prompt'){await navigator.clipboard.writeText(agentPrompt(data));if(current(v))toast('Agent instructions copied');}
   if(action==='refresh'){if(dirty)throw new Error('Save or cancel your role edits before refreshing.');await refresh(v);if(current(v))show();}
   if(action==='cancel-edit')show();
   if(action==='cancel-job'){if(!data.can_confirm)throw new Error('Only the project owner can cancel this request.');await mutate('cancel_crew_setup_job',{job_id:el.dataset.job});if(!current(v))return;await refresh(v);if(current(v))show();}
   if(action==='resume'){if(!data.can_confirm)throw new Error('Only the project owner can retry this operation.');await mutate('resume_crew_setup_job',{job_id:el.dataset.job});if(!current(v))return;await refresh(v);if(current(v))show();}
   if(action==='stop'){
    assertOwner();const h=hostFor(null,true);await mutate('request_crew_setup_job',jobArgs('stop',h));if(!current(v))return;await refresh(v);if(current(v))show();
   }
  }catch(err){if(current(v))error(err);}finally{if(current(v)){busy=false;schedule(v);}el.disabled=false;}
 });
 document.addEventListener('submit',async event=>{
  const form=event.target,roleForm=form.classList?.contains('crew-role-edit');
  if(!active||(!roleForm&&!['crew-start','crew-correct','crew-start-work','crew-suggest','crew-prepare','crew-create','crew-launch'].includes(form.id)))return;
  event.preventDefault();if(busy)return;busy=true;pausePoll();const v=epoch,submit=event.submitter;if(submit)submit.disabled=true;$('#crew-error').textContent='';
  try{
   let command,args;
   if(form.id==='crew-start'){
    if(!form.consent.checked)throw new Error('Review and confirm the selected context before saving.');
    if(!session.active_state)throw new Error('Import a saved project state before setting up the team.');
    command='start_crew_setup';args={session_id:session.id,state_id:session.active_state,organization_name:form.elements.organization_name.value.trim(),notes:form.notes.value,...await encodeSources(items)};
    if(form.organization_id.value.trim())args.organization_id=form.organization_id.value.trim();
   }else{
    assertOwner();if(dirty&&!roleForm&&form.id!=='crew-correct')throw new Error('Save or cancel your role edits before continuing.');if(data.stale)throw new Error('Project or organization changed. Start a fresh setup from the current context.');
    args={setup_id:data.id,version:data.version};
    if(form.id==='crew-correct'||roleForm){
     command='propose_crew_setup';args.input_basis=data.basis;
     if(roleForm){const val=name=>form.elements[name].value;args.proposal=editRole(data.proposal.content,Number(form.dataset.role),{name:val('role_name'),parent:val('parent'),mission:val('mission'),responsibilities:val('responsibilities'),scope:val('scope'),assign:form.elements.assign.checked,integrate:form.elements.integrate.checked});}
     else try{args.proposal=JSON.parse(form.proposal.value);}catch{throw new Error('Proposal must be valid JSON. Your edits have been kept.');}
    }
    if(form.id==='crew-suggest'||form.id==='crew-prepare'){
     if(form.id==='crew-suggest'&&!form.consent.checked)throw new Error('Confirm use of the saved context with your connected agent.');
     command='request_crew_setup_job';args=jobArgs(form.id==='crew-suggest'?'analyze':'prepare',hostFor(form));
     if(data.proposal)args.proposal_hash=data.proposal.hash;
    }
    if(form.id==='crew-create'||form.id==='crew-launch'){
     if(!form.consent.checked)throw new Error('Confirm the reviewed roles and runtime before continuing.');
     if(!readyPreparation(data,control))throw new Error('Refresh or prepare the runtime for this exact proposal.');
     const h=hostFor(form,true);command='request_crew_setup_job';args={...jobArgs(form.id==='crew-create'?'activate':'start',h),proposal_hash:data.proposal.hash,runtime_plan_hash:control.prepared.runtime_plan_hash};
     if(form.id==='crew-launch'){
      if(data.status!=='activated')throw new Error('Create the team before starting work.');
      const limits={max_parallel:Number(form.elements?.max_parallel?.value||team?.max_parallel||1),max_executions:form.elements?.max_executions?form.elements.max_executions.value.trim()?Number(form.elements.max_executions.value):null:team?.max_executions??null};
      if(!data.execution_enabled||limits.max_parallel!==team?.max_parallel||limits.max_executions!==team?.max_executions){
       const updated=await mutate('studio_execution_policy',{session_id:session.id,version:session.version,enabled:true,...limits});if(!current(v))return;
       data.execution_enabled=true;team={...team,...updated,...limits};session={...session,version:updated.version??session.version};
      }
      args.session_version=session.version;
     }
    }
    if(form.id==='crew-start-work'){if(!canStartWork(data))throw new Error('The lead runtime must be online with execution enabled.');command='start_crew_setup_work';}
   }
   if(!current(v))return;
   const result=await mutate(command,args);if(!current(v))return;
   if(command==='start_crew_setup'){location.hash=setupURL(result.session_id,result.id);return;}
   await refresh(v);if(!current(v))return;show();$('#main h1')?.focus();toast(command==='propose_crew_setup'?'Changes saved · prepare the updated runtime before approval':'Request saved');
  }catch(err){if(current(v))error(err);}finally{if(current(v)){busy=false;schedule(v);}if(submit)submit.disabled=false;}
 });
 return {render,leave:()=>{pausePoll();active=false;epoch++;items=[];data=null;team=null;intents.clear();busy=false;dirty=false;}};
}
