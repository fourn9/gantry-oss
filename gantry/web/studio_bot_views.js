import {esc as e,short} from './ui.js';
const button=(name,label,value='',extra='')=>`<button type="button" data-studio="${name}" data-value="${e(value)}" ${extra}>${label}</button>`;
export function requestStatus(r){
  if(r.status==='pending')return r.runtime?.presence==='online'?'Queued':'Queued · runtime offline';
  if(r.status==='running')return r.runtime?.presence==='online'?'Working':'Connection lost · recovery required';
  return ({waiting:'Waiting for reports',held:'Paused · recovery required',handoff_requested:'Handoff pending',completed:'Completed',blocked:'Needs attention',failed:'Failed',cancelled:'Stopped'})[r.status]||r.status;
}
export function requestActions(detail){
  return `<div class="studio-bot-actions">${detail.can_ask_bot?button('ask-bot','Ask Crew agent'):''}${detail.can_assign_bot?button('assign-bot','Assign work'):''}</div>`;
}
export function requestList(detail,selection){
  const same=r=>r.state_id===selection.state_id&&JSON.stringify(Object.entries(r.anchor).sort())===JSON.stringify(Object.entries(selection.anchor).sort());
  return (detail.bot_requests||[]).filter(same).map(r=>`<div class="studio-bot-request"><div><strong>${e(r.bot_name)}</strong><span>${e(r.mode==='ask'?'Question':'Assigned work')}</span></div>${r.body?`<p>${e(r.body.slice(0,180))}${r.body.length>180?'…':''}</p>`:''}${detail.can_comment?button('reply','Reply'):''}<p>${e(requestStatus(r))}</p>${r.body?.length>180||r.hold_reason?`<details><summary>Request details</summary>${r.body?.length>180?`<p>${e(r.body)}</p>`:''}${r.hold_reason?`<p>${e(r.hold_reason)}</p>`:''}</details>`:''}${r.result_work_id?`<a href="#studio-work/${encodeURIComponent(r.result_work_id)}">Open candidate →</a>`:''}${r.children?.length?`<details><summary>${r.children.length} delegated task${r.children.length===1?'':'s'}</summary>${r.children.map(c=>`<p>${e(c.bot_id)}${c.candidate_id?' · '+e(c.candidate_id):''} · ${e(c.status)}${c.change_id?` <a href="#studio-work/${encodeURIComponent(c.change_id)}">Open candidate</a>`:''}</p>`).join('')}</details>`:''}${r.can_handoff&&!['completed','failed','blocked','cancelled','handoff_requested'].includes(r.status)?button('handoff-bot','Hand off',r.id):''}${r.handoff?.phase==='requested'&&r.can_acknowledge?button('ack-handoff','Confirm executor stopped',r.id):''}${r.handoff?.phase==='ready'?'<small>Waiting for the receiving Bot to connect and accept.</small>':''}</div>`).join('');
}
export function teamView(team){
  if(!team.sessions.length)return '<p>Import a saved project and start work before configuring its team.</p>';
  return team.sessions.map(s=>`<section class="studio-team-session"><div class="studio-row"><strong>${e(s.title)}</strong>${s.can_configure?button('crew-setup','Initial team setup',s.id)+button('team-add','Add Bot',s.id):''}</div><p class="studio-small">${s.project?e(s.project.goal):'No team configured'} · ${s.mode==='execute'?'Assigned execution enabled':'Execution disabled'}</p>${s.bots.map(({bot:b,binding,runtime})=>`<div class="studio-team-member"><div><strong>${e(b.name)}</strong><small>${e(b.profile.mission)}${b.parent_bot_id?' · Reports to '+e(s.bots.find(r=>r.bot.id===b.parent_bot_id)?.bot.name||b.parent_bot_id):''}</small><small>${e(binding.write_scope.join(', ')||'Read only')} · ${e(binding.principal_id)}</small></div><div><span>${e(runtime.presence.replaceAll('_',' '))}</span>${s.can_view_guidance?button('bot-guidance','Guidance',s.id+'|'+b.id):''}${s.can_configure?button('team-edit','Edit',s.id+'|'+b.id)+button('bot-runtime','Runtime',s.id+'|'+b.id):''}</div></div>`).join('')||'<p>No Bots yet. Each Bot keeps its identity and experience across work.</p>'}<div class="studio-bot-actions">${s.can_configure?button('team-execution','Execution settings',s.id):''}${button('agent-connect','Connect a customer agent',s.id)}</div></section>`).join('')+'<p class="studio-small">Bots use your agent runtime and account. Opening this panel starts no process. Mentor is a separate, optional review workflow.</p>';
}
export function requestForm(s,detail,selection,mode,draft){
  const paths=selection.anchor.path?[selection.anchor.path]:detail.work.write_scope;
  const covers=r=>paths.every(p=>r.binding.write_scope.some(x=>x==='*'||p===x||p.startsWith(x.replace(/\/$/,'')+'/')));
  const bots=s.bots.filter(r=>r.bot.enabled&&r.binding.enabled).sort((a,b)=>Number(covers(b))-Number(covers(a)));
  return `<p>${e(detail.work.title)} · ${e(selection.anchor.path||'Entire work')}${selection.anchor.line?':'+selection.anchor.line:''} · ${e(short(selection.state_id))}</p><label>Bot<select name="bot" required>${bots.map(r=>`<option value="${e(r.bot.id)}">${e(r.bot.name)} · ${e(r.runtime.presence.replaceAll('_',' '))}</option>`).join('')}</select></label><label>${mode==='ask'?'Question':'Purpose'}<textarea name="body" required maxlength="4000">${e(draft||'')}</textarea></label>${mode==='assign'?`<label>Files or directories this Bot may change (one per line)<textarea name="scope" required>${e((selection.anchor.path?[selection.anchor.path]:detail.work.write_scope).join('\n'))}</textarea></label><label>Done when (one condition per line)<textarea name="completion" required></textarea></label>`:'<p>Read-only question. No file edits, tool execution, adoption or automatic assignment.</p>'}<p class="studio-small">${s.mode!=='execute'?'Execution is currently disabled. The request will wait until the owner enables it.': 'An offline Bot keeps the request queued until its customer runtime connects.'}</p>`;
}

export function guidanceView(view, bot, cursor) {
  const selected=view.selected;
  const ruleLabel=r=>r.scope==='phase'?r.phase:r.scope==='task'?'This task':'Project';
  const rules=view.rules.map(r=>`<p><strong>${e(r.key)}</strong> · ${e(ruleLabel(r))} · v${e(r.version)}${r.enabled?'':' · Withdrawn'}<br>${e(r.text)}<br><small>${e(r.author_id)} · ${e(r.reason)}</small> ${view.can_edit?button('guidance-edit','Edit',r.id):''}</p>`).join('');
  const lessons=(view.lessons||[]).map(m=>`<section><p>${e(m.strategy)}</p><p>Applies when ${e(m.when_to_use)} · Recheck when ${e(m.when_not_to_use.join(' / '))}</p>
    <p><small>Evidence ${e(m.evidence.map(short).join(', '))}</small></p>${button('guidance-task','Source task',m.source_task_id)} ${view.can_edit?button('guidance-correct','Correct this lesson',m.id):''}</section>`).join('');
  const history=(selected?.actions||[]).map(a=>`<li>${e(a.kind)} · ${e(a.rationale||'No declared rationale')} <small>${e(short(a.id))}</small></li>`).join('');
  const uses=(selected?.experience_uses||[]).map(u=>`<li>${e(u.change)} · ${e(u.condition_check)}<br><small>Memory ${e(short(u.memory_id))} · Actions ${e(u.action_ids.map(short).join(', '))}</small></li>`).join('');
  return `<p>${e(bot.profile.mission)} · ${e(view.phase||'Phase unrecorded')}</p>
    <div class="studio-row"><strong>Standing responsibility</strong>${view.can_delegate?button('guidance-delegate','Configure'):''}</div>
    <p>${view.continuation?.enabled?'Enabled':'Off'} · ${e(view.continuation?.completion.join(' / ')||'No standing delegation')}</p>
    ${view.commitments.map(c=>`<p>${e(c.summary)} · ${e(c.status)}</p>`).join('')}
    <div class="studio-row"><strong>Owner guidance</strong>${view.can_edit?button('guidance-edit','Add guidance'):''}</div>
    ${rules||'<p>No saved guidance.</p>'}${cursor?button('guidance-page','First page'):''}${view.next_cursor?button('guidance-page','Next page',view.next_cursor):''}
    ${lessons?`<details><summary>Recent lessons</summary>${lessons}</details>`:''}
    <details ${selected?'open':''}><summary>Recent work</summary>${view.tasks.map(t=>button('guidance-task',e(t.title)+' · '+e(t.status),t.id)).join(' ')}
    ${selected?`<p><strong>${e(selected.title)}</strong> · ${e(selected.status)}</p>${selected.reason?`<p>${e(selected.reason)}</p>`:''}
    <p>Recorded actions</p>${history?`<ol>${history}</ol>`:'<p>No actions recorded.</p>'}
    <p>Reported experience use</p>${uses?`<ul>${uses}</ul>`:'<p>No experience linked to an action.</p>'}`:''}</details>`;
}
