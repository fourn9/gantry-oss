import {$} from './ui.js';
import {intentKey} from './intent_key.js';
import * as views from './crew_setup_views.js';
import {sourceSelection,sourceSummary,encodeSources,agentPrompt,canStartWork,setupURL} from './crew_setup_model.js';
export function createCrewSetup({api,toast,fail}){
 let data,session,principals=[],items=[],epoch=0,active=false,busy=false,pending=null;
 const current=value=>active&&epoch===value;
 const show=()=>{$('#main').innerHTML=views.review(data,principals);};
 const error=err=>{const el=$('#crew-error');if(el)el.textContent=err.message;else fail(err);};
 async function loadPrincipals(sid,version){
  const details=await api('session_details',{session_id:sid});if(!current(version))return;
  const team=await api('studio_team',{project_id:details.session.project_id});if(!current(version))return;
  session=details.session;const row=team.sessions.find(s=>s.id===sid);principals=row?.principals||[];return row;
 }
 async function render(sid,id){
  const version=++epoch;active=true;busy=false;pending=null;items=[];data=null;$('#breadcrumb').textContent='Initial team setup';
  $('#main').innerHTML='<div class="studio-empty" role="status">Loading team setup…</div>';
  try{
   if(id){const result=await api('get_crew_setup',{setup_id:id});if(!current(version))return;if(result.session_id!==sid)throw new Error('This setup belongs to a different project session.');data=result;await loadPrincipals(sid,version);if(current(version))show();}
   else {const team=await loadPrincipals(sid,version);if(!current(version))return;const drafts=await api('list_crew_setups',{session_id:sid});if(!current(version))return;$('#main').innerHTML=views.start(session,drafts,team?.project?.organization_id?{id:team.project.organization_id,name:team.project.organization_name||''}:null);}
  }catch(err){if(current(version)){$('#main').innerHTML='<section class="onboarding"><h1>Unable to load team setup</h1><p id="crew-error" role="alert"></p><a href="#studio">Back to workspace</a></section>';error(err);}}
 }
 document.addEventListener('change',event=>{
  if(!active||busy)return;const el=event.target;
  if(el.name==='crew_sources'&&el.closest('#crew-start')){items=sourceSelection(el.files);$('#crew-source-preview').innerHTML=views.sources(items);}
  if(el.dataset.crewFile!==undefined){const item=items[Number(el.dataset.crewFile)];if(item&&!item.excluded)item.selected=el.checked;const s=sourceSummary(items);$('#crew-source-preview strong').textContent=`${s.count} exports · ${(s.size/1024/1024).toFixed(2)} MiB selected`;}
  if(el.dataset.crewProvider!==undefined){const item=items[Number(el.dataset.crewProvider)];if(item)item.provider=el.value;}
 });
 document.addEventListener('click',async event=>{
  const el=event.target.closest('[data-crew]');if(!active||busy||!el||el.disabled)return;event.preventDefault();const version=epoch;el.disabled=true;
  try{
   if(el.dataset.crew==='copy-prompt'){await navigator.clipboard.writeText(agentPrompt(data));if(current(version))toast('Customer-agent instructions copied');}
   if(el.dataset.crew==='refresh'){
    const result=await api('get_crew_setup',{setup_id:data.id});if(!current(version))return;await loadPrincipals(result.session_id,version);if(current(version)){data=result;pending=null;show();}
   }
  }catch(err){if(current(version))error(err);}finally{el.disabled=false;}
 });
 document.addEventListener('submit',async event=>{
  const form=event.target;if(!active||!['crew-start','crew-correct','crew-activate','crew-start-work'].includes(form.id))return;
  event.preventDefault();if(busy)return;busy=true;const version=epoch,submit=event.submitter;if(submit)submit.disabled=true;$('#crew-error').textContent='';
  try{
   let command,args;
   if(form.id==='crew-start'){
    if(!form.consent.checked)throw new Error('Review and confirm the selected context before saving.');
    if(!session.active_state)throw new Error('Import a saved project state before setting up the team.');
    command='start_crew_setup';args={session_id:session.id,state_id:session.active_state,organization_name:form.elements.organization_name.value.trim(),notes:form.notes.value,...await encodeSources(items)};
    if(form.organization_id.value.trim())args.organization_id=form.organization_id.value.trim();
   }else{
    if(!data.can_confirm)throw new Error('Only the project owner can make this change.');
    args={setup_id:data.id,version:data.version};
    if(data.stale)throw new Error('Project or organization changed. Start a fresh setup from the current context.');
    if(form.id==='crew-correct'){command='propose_crew_setup';args.input_basis=data.basis;try{args.proposal=JSON.parse(form.proposal.value);}catch{throw new Error('Proposal must be valid JSON. Your edits have been kept.');}}
    if(form.id==='crew-activate'){
     if(!form.consent.checked)throw new Error('Approve the exact proposal and agent mappings before activation.');
     if(!data.proposal||data.status==='activated')throw new Error('Refresh to review the current proposal.');
     command='activate_crew_setup';args.proposal_hash=data.proposal.hash;args.bindings=data.proposal.content.roles.map((r,i)=>({role_id:r.role_id,principal_id:form.elements['principal_'+i]?.value||''}));
     if(args.bindings.some(b=>!principals.some(p=>p.id===b.principal_id)))throw new Error('Map every role to an eligible customer agent identity.');
     if(new Set(args.bindings.map(b=>b.principal_id)).size!==args.bindings.length)throw new Error('Each role needs a separate dedicated agent identity.');
    }
    if(form.id==='crew-start-work'){if(!canStartWork(data))throw new Error('Refresh readiness. The lead runtime must be online and execution enabled.');command='start_crew_setup_work';}
   }
   if(!current(version))return;
   const signature=JSON.stringify([command,args]);if(!pending||pending.signature!==signature)pending={signature,key:intentKey()};
   const result=await api(command,args,pending.key);if(!current(version))return;
   if(command==='start_crew_setup'){pending=null;location.hash=setupURL(result.session_id,result.id);return;}
   // Mutation replies are followed by a saved view, never assumed readiness.
   const saved=await api('get_crew_setup',{setup_id:data.id});if(!current(version))return;pending=null;data=saved;show();$('#main h1')?.focus();toast(command==='activate_crew_setup'?'Team activated · configure customer runtimes next':command==='start_crew_setup_work'?'First planning task queued':'Corrected proposal saved · review before activation');
  }catch(err){if(current(version))error(err);}finally{if(current(version))busy=false;if(submit)submit.disabled=false;}
 });
 return {render,leave:()=>{active=false;epoch++;items=[];data=null;principals=[];pending=null;busy=false;}};
}
