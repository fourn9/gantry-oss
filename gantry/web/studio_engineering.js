import {esc as e,short} from './ui.js';
import {libraryURL} from './studio_model.js';

const text=value=>typeof value==='string'?value:JSON.stringify(value??null);
const array=value=>Array.isArray(value)?value:[];
const list=items=>`<ul>${array(items).map(x=>`<li>${e(typeof x==='string'?x:x?.reason||x?.code||text(x))}</li>`).join('')}</ul>`;
function observation(o,detail,subject){
 const p=o.provenance||{},s=p.source||{},pid=detail.work?.project_id;
 const label=`${s.path||'Source unavailable'}${s.locator?' · '+s.locator:''}`;
 const source=pid&&p.state_id&&s.path&&s.sha256?`<a href="#${e(libraryURL(pid,subject?.namespace==='hierarchy'?subject.id:'','files',p.state_id,{kind:'file',path:s.path,hash:s.sha256}))}">${e(label)}</a>`:e(label);
 return `<div class="studio-evidence-observation"><span>${e(text(o.value))}${o.unit?' '+e(o.unit):''}</span><small>${e(o.classification||'unknown')} · ${e(o.method||'Method not recorded')}${o.frame?' · '+e(o.frame):''}${o.time_basis?' · '+e(o.time_basis):''}</small><small>${source} · ${e(short(p.state_id||''))}</small></div>`;
}
export function engineeringEvidence(detail){
 const a=detail.design_assessment,x=a?.engineering_evidence;
 if(!x)return '';
 return `<details class="studio-context studio-evidence"><summary>Change impact &amp; evidence</summary><p class="studio-small">${e(short(a.baseline_state_id))} → ${e(short(a.state_id))} · Saved state comparison. Extracted or declared values are not verification results.</p>${x.coverage?.partial||a.partial?'<p class="studio-small">Partial evidence — some records are omitted. Use the assessment API and source views for the complete context.</p>':''}${x.fields?.length?`<div class="studio-evidence-scroll"><table class="studio-checks"><thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead><tbody>${x.fields.map(f=>`<tr><td>${e(f.name)}<small>${e(f.subject?.id||'Unknown subject')} · ${e(f.status)}</small></td><td>${(f.before||[]).map(o=>observation(o,detail,f.subject)).join('')||'Not acquired'}</td><td>${(f.after||[]).map(o=>observation(o,detail,f.subject)).join('')||'Not acquired'}</td></tr>`).join('')}</tbody></table></div>`:'<p class="studio-small">No comparable fields acquired. This does not establish absence of impact.</p>'}${array(x.impacts).length?`<details><summary>Potential impact (${x.impacts.length})</summary>${list(x.impacts.map(i=>(i.target?.id||'Unknown component')+' · '+array(i.changed_inputs).join(', ')+(array(i.via).length?' · via '+i.via.map(v=>v.prerequisite+' → '+v.dependent).join(', '):'')+(array(i.check_ids).length?' · checks: '+i.check_ids.join(', '):'')))}</details>`:''}${x.check_obligations?.length?`<details><summary>Checks to consider</summary>${list(x.check_obligations.map(c=>c.id+' · '+c.status+' · '+(c.reasons||[]).join(', ')))}</details>`:''}${x.conflicts?.length?`<details><summary>Conflicting evidence (${x.conflicts.length})</summary>${list(x.conflicts)}</details>`:''}${x.unknowns?.length?`<details><summary>Missing or uncertain (${x.unknowns.length})</summary>${list(x.unknowns)}</details>`:''}</details>`;
}

export function verificationPlans(detail){
 const data=detail.verification_plans;if(!data?.items?.length)return '';
 return `<details class="studio-context studio-evidence"><summary>Verification plans (${data.items.length})</summary><p class="studio-small">A plan is not an execution result. Checks above show results on the selected version.</p>${data.items.map(({result:p})=>`<details><summary>${e(p.question||p.purpose||'Verification plan')} · ${e(p.status)}</summary><p>${e(p.purpose)}</p><p class="studio-small">${p.input_state===detail.selected.state.id?'Selected version':'Previous / other version'} · ${e(short(p.input_state||''))} · Tool: ${e(p.tool?.name||'Unavailable')}</p>${array(p.checks).length?list(p.checks.filter(c=>c&&typeof c==='object').map(c=>c.id+' · '+c.scope)):''}${array(p.missing).length?list(p.missing):''}${array(p.assumptions).length?`<p class="studio-small">Assumptions</p>${list(p.assumptions)}`:''}<dl class="context-list">${['pass','fail','unknown'].map(k=>`<dt>${e(k)}</dt><dd>${e(p.next_steps?.[k]||'Not recorded')}</dd>`).join('')}</dl></details>`).join('')}${data.partial?'<p class="studio-small">Partial plan history. Retrieve full task action records through the API.</p>':''}</details>`;
}
