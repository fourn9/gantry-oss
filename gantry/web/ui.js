export const $ = (selector, root=document) => root.querySelector(selector);
export const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths={sessions:'M4 4h16v12H9l-5 4V4Z',inbox:'M4 4h16v16H4V4Zm0 10h5l1 3h4l1-3h5',projects:'M3 6h7l2 2h9v12H3V6Z',integrations:'m8 3 3 3-5 5-3-3m10 13-3-3 5-5 3 3M9 15l6-6',queued:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4v5l3 2',running:'m9 5 9 7-9 7V5Z',review:'m5 12 4 4L19 6',attention:'m12 3 10 18H2L12 3Zm0 6v5m0 3v1',done:'m5 12 4 4L19 6',code:'m8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16',github:'M8 19c-4 1-4-2-6-2m12 5v-4a4 4 0 0 0-1-3c4 0 6-2 6-5 0-2-1-3-2-4 0-1 0-3-1-3-2 0-3 1-4 1-2 0-3-1-5-1-1 0-1 2-1 3-1 1-2 2-2 4 0 3 2 5 6 5-1 1-1 2-1 3v4'};
export const icon=name=>`<svg class="icon" aria-hidden="true" viewBox="0 0 24 24"><path d="${paths[name]||paths.projects}"/></svg>`;
export const short=id=>id ? id.replace(/^[a-z]+_/,'').slice(0,8) : 'Not captured';
export const time=ms=>ms?new Date(ms).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'Never';
export const relative=ms=>{if(!ms)return 'Never';const m=Math.max(0,Math.floor((Date.now()-ms)/60000));return m<1?'Just now':m<60?`${m}m ago`:m<1440?`${Math.floor(m/60)}h ago`:`${Math.floor(m/1440)}d ago`;};
export const labels={queued:'Queued',running:'Running',review:'Waiting for review',attention:'Needs attention',done:'Done'};
export const badge=(value,label)=>`<span class="badge ${esc(value)}">${esc(label||labels[value]||String(value).replaceAll('_',' '))}</span>`;
export const empty=(title,body,action='')=>`<div class="empty"><h2>${esc(title)}</h2><p>${esc(body)}</p>${action}</div>`;
export const button=(action,label,id='',klass='')=>`<button class="${esc(klass)}" data-action="${esc(action)}" data-id="${esc(id)}">${esc(label)}</button>`;
export const options=(items,key='id',label='name',selected='')=>items.map(x=>`<option value="${esc(x[key])}" ${x[key]===selected?'selected':''}>${esc(x[label])}</option>`).join('');
export const safeLink=(url,label)=>{try {const u=new URL(url);return u.protocol==='https:'?`<a href="${esc(u.href)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:esc(label);}catch{return esc(label);}};
export const diffText=text=>`<pre class="diff-code">${String(text||'').split('\n').map(line=>`<span class="diff-line ${line.startsWith('+')?'add':line.startsWith('-')?'remove':line.startsWith('@@')?'hunk':''}">${esc(line)||' '}</span>`).join('')}</pre>`;
export function toast(text){const el=$('#toast');el.textContent=text;el.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.hidden=true,4200);}
export function download(name,body,type='application/json'){const url=URL.createObjectURL(new Blob([body],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
