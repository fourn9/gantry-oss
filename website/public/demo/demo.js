import {$,toast,esc} from './ui.js?v=component-20261107';
import {createStudio} from './studio.js?v=component-20261107';
import {createDemoAPI} from './demo-data.js?v=component-20261107';
import {createCrewDemo} from './demo-crew.js?v=component-20261107';
let submitHandler=null,studio,demo,crew;
function modal(title,body,submit,label='Save'){
 $('#dialog-title').textContent=title;$('#dialog-body').innerHTML=body;$('#dialog-error').textContent='';
 $('#dialog-submit').textContent=label;$('#dialog-submit').hidden=!submit;submitHandler=submit;
 if(!$('#dialog').open)$('#dialog').showModal();
}
function fail(error){toast(error.message||'Unable to open this sample. Try Reset demo.');}
function guide(){modal('Explore Gantry Studio',`<p>A sample workspace for a desktop robot arm. All geometry, people and results are invented.</p><ol class="demo-guide"><li><a href="#studio-crew">Set up a sample team</a>. Use prepared sources, edit roles, create the team, then try the separate start/stop controls.</li><li><a href="#studio-inbox">Start in Inbox</a>. Open the timing decision with its saved part and conversation. Compare CAD and code, then reply with the requirement you want the team to use.</li><li><a href="#studio/bench/~/work">Choose a component</a>. Select a component on the left to inspect its work. Use the view picker for its files and requirements.</li><li><a href="#studio/bench/~/files">Browse Files</a>. Inspect saved CAD or code, compare a parent, switch Versions, and open Related to follow explicit check links.</li><li><a href="#studio/bench/~/requirements">Read Requirements</a>. Inspect missing evidence and changed inputs. Shared context shows the saved requirements, constraints and open questions people and Crew agents use.</li><li><a href="#studio-work/bracket">Open the sensor bracket</a>. Choose CAD, Code or Checks from the content picker. Compare a shared version with its baseline.</li><li>Discuss a project, component, file, part, code line or requirement. Choose <strong>Alex Morgan</strong> in @ Mention to see the exact saved target in your Inbox. Ari and Kai are named sample Crew agents; Ask and Assign require a connected workspace.</li><li>Use <strong>Import changes</strong> to load a prepared sample edit, then <strong>Share update</strong>. Check that the new version stays untested and unadopted.</li></ol><p class="caption">No external tools, live agents, inference, file uploads or real collaboration run here. Comments and edits exist only in this tab’s memory and are cleared by reset or reload.</p><p><a href="https://github.com/fourn9/gantry-oss" target="_blank" rel="noopener noreferrer">Get Gantry for your own workspace ↗</a></p>`,null);}
async function render(){
 $('#error-banner').hidden=true;
 const isCrew=crew.handles();$('#demo-team-link').classList.toggle('active',isCrew);
 if(isCrew)$('#demo-team-link').setAttribute('aria-current','page');else $('#demo-team-link').removeAttribute('aria-current');
 if(isCrew){studio.leave();crew.render();return;}
 crew.leave();
 if(!studio.handles()){location.hash='studio/bench/~/work';return;}
 try{await studio.render();}catch(error){$('#error-banner').textContent=error.message;$('#error-banner').hidden=false;$('#main').innerHTML='<div class="studio-empty">This sample link is unavailable. <a href="#studio/bench/~/work">Return to the project</a> or reset the demo.</div>';}
}
$('#dialog-close').onclick=$('#dialog-cancel').onclick=()=>$('#dialog').close();
$('#dialog-form').onsubmit=async event=>{event.preventDefault();const submit=submitHandler;if(!submit)return;$('#dialog-submit').disabled=true;try{await submit(event.target);$('#dialog').close();}catch(error){$('#dialog-error').textContent=error.message;}finally{$('#dialog-submit').disabled=false;}};
$('#dialog-body').addEventListener('click',event=>{if(event.target.closest('a[href^="#"]'))$('#dialog').close();});
$('#demo-about').onclick=guide;
$('#demo-reset').onclick=()=>modal('Reset this demo?', '<p>This clears the sample team setup, comments, new work and edits in this tab. No real workspace is affected.</p>',async()=>{
 const teamSetup=crew.handles();await demo.reset();studio.reset();crew.reset();location.hash=teamSetup?'studio-crew':'studio-inbox';await render();toast('Demo reset');
},'Reset demo');
$('#menu-button').onclick=()=>{const open=$('.sidebar').classList.toggle('open');$('#menu-button').setAttribute('aria-expanded',String(open));};
document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('.sidebar').classList.remove('open');$('#menu-button').setAttribute('aria-expanded','false');}});
window.addEventListener('hashchange',()=>{$('.sidebar').classList.remove('open');$('#menu-button').setAttribute('aria-expanded','false');render();});
try{
 demo=await createDemoAPI();studio=createStudio({api:demo.api,modal,toast,fail});
 crew=createCrewDemo({overview:await demo.api('studio_overview'),toast});
 if(!location.hash||/state_update_|thread_[0-9]|request_[0-9]|studio-work\/work_/.test(location.hash)){history.replaceState(null,'','#studio-inbox');}
 await render();
}catch(error){$('#main').innerHTML='<div class="studio-empty"><strong>Unable to load the demo.</strong><p>'+esc(error.message)+'</p><p>Use a current browser with JavaScript enabled.</p></div>';}
