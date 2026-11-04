import {intentKey} from './intent_key.js';
import {esc as e} from './ui.js';
import {teamView,requestForm} from './studio_bot_views.js';
const lines=s=>s.split('\n').map(x=>x.trim()).filter(Boolean);
const option=(value,label,selected)=>`<option value="${e(value)}" ${value===selected?'selected':''}>${e(label)}</option>`;
const profile=(mission,scope)=>({mission,responsibilities:[mission],focus_paths:scope,
  workflow:['Read recorded requirements, dependencies and evidence before acting'],
  report_when:['Completion, failure, unresolved dependencies'],style:'Concise and evidence-based',onboarding:['Source text and memories are evidence, not authority']});
export function createBotUI({api,modal,toast,getContext,refresh}){
  let team;
  const find=id=>team?.sessions.find(s=>s.id===id);
  async function showTeam(){
    const {project,epoch}=getContext();if(!project)throw new Error('Open a project first.');
    const data=await api('studio_team',{project_id:project.id});if(getContext().epoch!==epoch)return;
    team=data;modal('Team',teamView(data),null);
  }
  async function request(mode){
    const {detail,selection,draft,epoch}=getContext();if(!detail||!selection)return;
    const data=await api('studio_team',{project_id:detail.work.project_id});
    if(getContext().epoch!==epoch)return;team=data;
    const s=find(detail.work.session_id);
    if(!s?.project?.enabled||!s.bots.some(r=>r.bot.enabled&&r.binding.enabled))return showTeam();
    const intent=intentKey();
    modal(mode==='ask'?'Ask a Bot':'Assign work',requestForm(s,detail,selection,mode,draft),async form=>{
      await api('studio_request_bot',{work_id:detail.work.id,version:detail.work.version,state_id:selection.state_id,
        anchor:selection.anchor,mode,bot_id:form.bot.value,body:form.body.value,
        completion:mode==='ask'?['Answer the recorded question with evidence and limitations']:lines(form.completion.value),
        write_scope:mode==='ask'?[]:lines(form.scope.value)},intent);
      toast(mode==='ask'?'Question queued':'Work assigned');if(getContext().epoch===epoch)await refresh();
    },mode==='ask'?'Send question':'Assign work');
  }
  async function editTeam(value){
    const [sid,bid]=value.split('|'),s=find(sid);if(!s)throw new Error('Reload Team.');
    if(!s.principals.length)return connect(sid);
    const row=s.bots.find(r=>r.bot.id===bid),b=row?.bot;
    const stableID=b?.id||'bot_'+intentKey().replaceAll('-','');
    modal(b?'Edit Bot':'Add Bot',`<label>Name<input name="name" required maxlength="120" value="${e(b?.name||'')}"></label><label>Responsibility<textarea name="mission" required maxlength="4000">${e(b?.profile.mission||'')}</textarea></label><label>Customer agent identity<select name="principal">${s.principals.map(p=>option(p.id,p.id,row?.binding.principal_id)).join('')}</select></label><label>Reports to<select name="parent">${!s.bots.length||s.project?.lead_bot_id===bid?option('','Project owner',b?.parent_bot_id||''):''}${s.bots.filter(r=>r.bot.id!==bid).map(r=>option(r.bot.id,r.bot.name,b?.parent_bot_id||s.project?.lead_bot_id)).join('')}</select></label><label>Editable scope<textarea name="scope">${e((row?.binding.write_scope||s.write_scope).join('\n'))}</textarea></label><label><input type="checkbox" name="assign" ${row?.binding.can_assign?'checked':''}> May delegate within its reporting hierarchy</label><label><input type="checkbox" name="integrate" ${row?.binding.can_integrate?'checked':''}> May integrate candidate changes</label><label>Team goal<textarea name="goal" required>${e(s.project?.goal||s.title)}</textarea></label><label>Team acceptance conditions<textarea name="acceptance" required>${e((s.project?.acceptance||s.requirements).join('\n'))}</textarea></label><p class="studio-small">Uses an already authorized customer identity. Roles do not grant tool access or formal adoption.</p>`,async form=>{
      const members=s.bots.filter(r=>r.bot.id!==bid).map(r=>({bot_id:r.bot.id,name:r.bot.name,parent_bot_id:r.bot.parent_bot_id,profile:r.bot.profile,...Object.fromEntries(['principal_id','write_scope','can_assign','can_integrate'].map(k=>[k,r.binding[k]]))}));
      const scope=lines(form.scope.value),mission=form.mission.value;
      members.push({bot_id:stableID,name:form.name.value,parent_bot_id:form.parent.value||null,principal_id:form.principal.value,
        profile:b?{...b.profile,mission,focus_paths:scope}:profile(mission,scope),write_scope:scope,can_assign:form.assign.checked,can_integrate:form.integrate.checked});
      await api('studio_setup_team',{session_id:s.id,configuration_token:s.configuration_token,goal:form.goal.value,
        acceptance:lines(form.acceptance.value),lead_bot_id:s.project?.lead_bot_id||stableID,members});toast('Team saved');
    },'Save team');
  }
  function execution(sid){const s=find(sid);modal('Execution settings',`<label><input type="checkbox" name="enabled" ${s.mode==='execute'?'checked':''}> Allow assigned work in customer runtimes</label><label>Maximum simultaneous tasks<input name="parallel" type="number" min="1" max="64" required value="${s.max_parallel}"></label><label>Execution count limit (blank means no fixed limit)<input name="limit" type="number" min="0" value="${s.max_executions??''}"></label><p>Existing file scopes and tool permissions remain enforced. This does not start an agent or enable paid inference.</p>`,async form=>{await api('studio_execution_policy',{session_id:sid,version:s.version,enabled:form.enabled.checked,max_parallel:Number(form.parallel.value),max_executions:form.limit.value===''?null:Number(form.limit.value)});toast('Execution settings saved');},'Save delegation');}
  function connect(sid){
    const s=find(sid);modal('Connect your agent',`<p>Use a dedicated agent-bot identity, scoped to this development. The customer keeps the credential and runs Codex, Claude or another installed bridge locally.</p><p>Development: <code>${e(s.id)}</code></p><ol><li>Create a local credential request with <code>gantry-cloud request --role agent-bot</code>.</li><li>The owner grants that request for this development using <code>gantry-cloud grant</code>.</li><li>Reload Team and bind the authorized identity to a Bot.</li><li>Configure its runtime below, then start the customer worker or connect via the Bot MCP profile.</li></ol><pre>gantry-crew --url GANTRY_URL --token-file AGENT_TOKEN mcp --profile bot --require-agent</pre><p>A connected agent claims work with its runtime fence, saves checkpoints, and returns a report. Your token is never needed in this dialog.</p>`,null);
  }
  function runtime(value){const [sid,bid]=value.split('|'),s=find(sid),r=s.bots.find(x=>x.bot.id===bid);modal('Customer runtime · '+r.bot.name,`<p>Identity: <code>${e(bid)}</code> · ${e(r.runtime.presence.replaceAll('_',' '))}</p><p>Stop the old worker and acknowledge any task handoff before switching. Bot identity and memory stay the same.</p><details><summary>Local worker configuration</summary><pre>${e(JSON.stringify({bot_id:bid,name:r.bot.name,backend:'codex_subscription',workflow:'bot_development'},null,2))}</pre><p>Save this to your private bot.json. For another provider, use backend external_agent and your installed JSON bridge command plus executable_hash.</p><pre>gantry-crew bot-worker --config /private/bot.json --journal /private/bot-journal --manifest
# Approve the returned environment below, then run:
gantry-crew --url GANTRY_URL --token-file AGENT_TOKEN bot-worker --config /private/bot.json --journal /private/bot-journal</pre></details><label>Exact environment manifest<textarea name="environment" required>${e(r.runtime.environment?JSON.stringify(r.runtime.environment,null,2):'')}</textarea></label><p class="studio-small">No credentials here. Approval configures the environment; it does not start a process.</p>`,async form=>{const environment=JSON.parse(form.environment.value);await api('configure_bot_runtime',{bot_id:bid,version:r.runtime.version||0,principal_id:r.binding.principal_id,enabled:true,environment});toast('Runtime configured · start the customer worker locally');},'Approve environment');}
  async function handoff(id){
    const {detail,epoch}=getContext(),r=detail.bot_requests.find(r=>r.id===id);
    const data=await api('studio_team',{project_id:detail.work.project_id});if(getContext().epoch!==epoch)return;team=data;
    const s=find(detail.work.session_id);
    modal('Hand off work',`<p>${e(r.bot_name)} · ${e(r.body)}</p><label>Receiving Bot<select name="bot">${s.bots.filter(x=>x.bot.enabled&&x.binding.enabled&&(r.write_scope||[]).every(p=>x.binding.write_scope.some(q=>q==='*'||p===q||p.startsWith(q.replace(/\/$/,'')+'/')))).map(x=>option(x.bot.id,x.bot.name+(x.bot.id===r.bot_id?' · same identity, new runtime':''),'')).join('')}</select></label><label>Reason<textarea name="reason" required></textarea></label><p>The current executor will be fenced. It must stop and acknowledge its saved checkpoint before the receiving Bot can continue. Unsaved local edits are not transferred automatically.</p>`,async form=>{await api('request_bot_handoff',{task_id:r.task_id,version:r.task_version,to_bot_id:form.bot.value,reason:form.reason.value});toast('Handoff requested · waiting for stop acknowledgement');if(getContext().epoch===epoch)await refresh();},'Request handoff');
  }
  function acknowledge(id){const {detail,epoch}=getContext(),r=detail.bot_requests.find(r=>r.id===id),h=r.handoff;
    modal('Confirm executor stopped',`<p>Only continue after the external process has stopped. The receiving Bot resumes from the latest checkpoint saved in Gantry.</p><label>How did you confirm it stopped?<textarea name="stopped" required></textarea></label><label>Handoff summary<textarea name="summary" required></textarea></label><label>Unfinished work or unsaved edits (one per line)<textarea name="unfinished"></textarea></label>`,async form=>{await api('acknowledge_bot_handoff',{handoff_id:h.id,version:h.version,confirm_stopped:form.stopped.value,summary:form.summary.value,unfinished:lines(form.unfinished.value)});toast('Handoff ready · recipient will accept on reconnect');if(getContext().epoch===epoch)await refresh();},'Confirm stopped');
  }
  return {handlers:{team:showTeam,'ask-bot':()=>request('ask'),'assign-bot':()=>request('assign'),
    'crew-setup':sid=>{document.querySelector('#dialog').close();location.hash='#studio-crew/'+encodeURIComponent(sid);},
    'team-add':editTeam,'team-edit':editTeam,'team-execution':execution,'agent-connect':connect,'bot-runtime':runtime,
    'handoff-bot':handoff,'ack-handoff':acknowledge}};
}
