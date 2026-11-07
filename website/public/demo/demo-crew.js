import {$} from './ui.js?v=library-20261107';
import {sidebar} from './studio_views.js?v=library-20261107';
import {createDemoCrew} from './demo-crew-model.js?v=library-20261107';
import {crewView} from './demo-crew-views.js?v=library-20261107';

export function createCrewDemo({overview,toast}){
 const model=createDemoCrew();let active=false,dirtyForm=null;
 const handles=()=>location.hash==='#studio-crew';
 const show=(focus=false)=>{$('#main').innerHTML=crewView(model.snapshot());dirtyForm=null;if(focus)$('#main h1')?.focus();};
 const error=err=>{const el=$('#demo-crew-error');el.textContent=err.message;el.focus();};
 function render(){
  active=true;document.body.classList.add('studio-mode');$('#main').className='studio-main';$('#breadcrumb').textContent='Team setup';
  const side=sidebar(overview,[],{project:'bench'});$('#nav').innerHTML=side.nav;$('#sidebar-projects').innerHTML=side.projects;$('#recent-sessions').innerHTML=side.recent;show();
 }
 document.addEventListener('input',event=>{
  if(!active||!handles())return;const form=event.target.closest('.demo-crew-role-edit');if(!form)return;dirtyForm=form;
  document.querySelectorAll('.demo-crew-role-edit fieldset').forEach(fieldset=>fieldset.disabled=fieldset.form!==form);
  document.querySelectorAll('[data-demo-crew="prepare"],[data-demo-crew="create"]').forEach(el=>el.disabled=true);
 });
 document.addEventListener('click',event=>{
  const el=event.target.closest('[data-demo-crew]');if(!active||!handles()||!el||el.disabled)return;event.preventDefault();
  try{
   const action=el.dataset.demoCrew;
   if(action==='cancel-edit'){show(true);return;}
   if(dirtyForm)throw new Error('Save or cancel your role edits before continuing.');
   const actions={'load-sources':()=>model.loadSources(),suggest:()=>model.suggest(),prepare:()=>model.prepare(),create:()=>model.create(),start:()=>model.start(),stop:()=>model.stop()};
   if(!actions[action])return;actions[action]();show(true);
  }catch(err){error(err);}
 });
 document.addEventListener('submit',event=>{
  const form=event.target;if(!active||!handles()||!form.matches('.demo-crew-role-edit'))return;event.preventDefault();
  try{
   if(dirtyForm&&dirtyForm!==form)throw new Error('Save or cancel the role you are editing first.');
   const value=name=>form.elements[name].value;
   model.saveRole(Number(form.dataset.role),{name:value('role_name'),parent:value('parent'),mission:value('mission'),responsibilities:value('responsibilities'),scope:value('scope'),assign:form.elements.assign.checked,integrate:form.elements.integrate.checked});
   show(true);toast('Role saved · prepare the updated sample team');
  }catch(err){error(err);}
 });
 return {handles,render,leave:()=>{active=false;dirtyForm=null;},reset:()=>{model.reset();dirtyForm=null;}};
}
