import {$} from './ui.js';
import * as views from './onboarding_views.js';
import {folderSelection,encodeSelection,agentPrompt} from './onboarding_model.js';
export function createOnboarding({api,modal,toast,fail}){
 let data,items=[],epoch=0,active=false,pending=null;
 const ref=()=>({onboarding_id:data.id,version:data.version});
 const error=err=>{const el=$('#onboarding-error');if(el)el.textContent=err.message;else fail(err);};
 const show=()=>{$('#main').innerHTML=views.review(data);};
 async function render(id,overview){const current=++epoch;active=true;items=[];$('#breadcrumb').textContent='Project setup';
  if(id){const d=await api('get_onboarding',{onboarding_id:id});if(current!==epoch||!active)return;data=d;show();}
  else {const drafts=await api('list_onboardings');if(current!==epoch||!active)return;data=null;$('#main').innerHTML=views.start(drafts,overview);}
 }
 function scope(){const target=$('#onboarding-scope');if(target)target.innerHTML=views.scope(items);}
 document.addEventListener('change',event=>{if(!active)return;const el=event.target;
  if(el.name==='folder'&&el.closest('#onboarding-start')){items=folderSelection(el.files);pending=null;scope();const form=el.form;if(form.state)form.state.value='';if(!form.elements.name.value)form.elements.name.value=el.files[0]?.webkitRelativePath?.split('/')[0]||'';}
  if(el.dataset.file!==undefined){const item=items.find(x=>x.path===el.dataset.file);if(item)item.selected=el.checked;pending=null;const summary=$('#onboarding-scope strong');if(summary){const chosen=items.filter(x=>x.selected);summary.textContent=`${chosen.length} files · ${(chosen.reduce((n,x)=>n+x.file.size,0)/1024/1024).toFixed(2)} MiB selected`;}}
  if(el.name==='state'&&el.closest('#onboarding-start')&&el.value){items=[];$('#onboarding-scope').textContent='Using the exact saved project state; no local files will be uploaded.';pending=null;}
 });
 document.addEventListener('click',async event=>{const el=event.target.closest('[data-onboarding]');if(!active||!el||el.disabled)return;event.preventDefault();const current=epoch;el.disabled=true;
  try{const action=el.dataset.onboarding;
   if(action==='select-all'||action==='select-none'){items.forEach(x=>x.selected=!x.excluded&&action==='select-all');pending=null;scope();}
   if(action==='refresh'){data=await api('get_onboarding',{onboarding_id:data.id});if(current===epoch&&active)show();}
   if(action==='copy-prompt'){await navigator.clipboard.writeText(agentPrompt(data));toast('Agent handoff copied');}
   if(action==='edit-node'){const captured=data,node=data.hierarchy.find(x=>x.id===el.dataset.node);modal('Correct component',views.editNode(data,node),async form=>{
    const result=await api('correct_onboarding',{onboarding_id:captured.id,version:captured.version,node_id:node.id,title:form.title.value,
      parent:form.parent.value||'__root__',paths:form.paths.value.split('\n').map(x=>x.trim()).filter(Boolean),reason:form.reason.value});
    if(current===epoch&&active){data=result;show();}
   },'Save correction');}
  }catch(err){if(current===epoch&&active)error(err);}finally{el.disabled=false;}
 });
 document.addEventListener('submit',async event=>{const form=event.target;if(!active||!(form.id==='onboarding-start'||form.id==='onboarding-complete'||form.id==='onboarding-collaborators'||form.matches('.onboarding-question')))return;
  event.preventDefault();const current=epoch;event.submitter.disabled=true;$('#onboarding-error').textContent='';
  try{let result;
   if(form.id==='onboarding-start'){
    if(!form.consent.checked)throw new Error('Confirm the selected scope before saving.');
    const args={name:form.elements.name.value.trim(),goal:form.goal.value.trim(),actors:form.actors.value.split(',').map(x=>x.trim()).filter(Boolean),missing:[]};
    if(form.state.value){const state=await api('get_development_state',{state_id:form.state.value});args.snapshot=state.state.snapshot;args.missing=['Only the selected saved state; no live synchronization was started'];}
    else {args.files=await encodeSelection(items);args.missing=['Only selected saved files; excluded files and external dependencies were not captured'];}
    if(!active||current!==epoch)return;
    const signature=JSON.stringify(args);if(!pending||pending.signature!==signature)pending={signature,key:crypto.randomUUID()};
    event.submitter.textContent='Saving and inspecting…';result=await api('start_onboarding',args,pending.key);
    if(!active||current!==epoch)return;pending=null;location.hash='#studio-start/'+result.id;return;
   }
   if(form.id==='onboarding-complete'){result=await api('complete_onboarding',{...ref(),title:form.title.value,purpose:form.purpose.value});
    if(!active||current!==epoch)return;toast('Project ready · Not tested or adopted');location.hash=event.submitter.dataset.next==='crew'?'#studio-crew/'+encodeURIComponent(result.result.change.session_id):'#studio-work/'+result.result.change.id;return;}
   if(form.id==='onboarding-collaborators'){result=await api('set_onboarding_collaborators',{...ref(),actors:form.actors.value.split(',').map(x=>x.trim()).filter(Boolean)});if(current===epoch&&active){data=result;show();}return;}
   result=await api('answer_onboarding',{...ref(),question_id:form.dataset.question,answer:form.answer.value});
   if(current===epoch&&active){data=result;show();$('#main h1')?.focus();}
  }catch(err){if(current===epoch&&active)error(err);}finally{event.submitter.disabled=false;if(form.id==='onboarding-start')event.submitter.textContent='Inspect selected work';}
 });
 return {render,leave:()=>{active=false;epoch++;items=[];data=null;pending=null;}};
}
