// A request always reopens its recorded artifact and version, independent of the last tab.
export function requestContext(detail,threadId){
 const t=detail.threads.find(t=>t.id===threadId);if(!t)return null;
 const current=detail.versions.findIndex(v=>v.id===t.state_id),previous=detail.versions.findIndex(v=>v.id===t.compare_state_id);
 const compare=previous>=0&&previous<current;
 return {tab:t.anchor.kind==='code'?'code':'cad',file:t.anchor.path||'',part:t.anchor.part||'',compare,compareState:compare?t.compare_state_id:'',related_anchor:t.related_anchor||null,conversation:{anchor:t.anchor,state_id:t.state_id,thread_id:t.id}};
}
export function componentScope(nodes,id,override=''){
 const node=nodes.find(n=>n.id===id);if(!node)throw new Error('Choose a component.');
 const allowed=[...new Set(node.paths)];
 const paths=override.trim()?override.split(/\r?\n/).map(p=>p.trim()).filter(Boolean):allowed;
 if(!paths.length)throw new Error('This component has no mapped files.');
 if(paths.some(p=>p.startsWith('/')||p.includes('\\')||p.split('/').some(s=>s==='..'||s==='.')||!allowed.some(a=>p===a||(a.endsWith('/')&&p.startsWith(a)))))throw new Error('Paths must stay within the selected component.');
 return [...new Set(paths)].filter(p=>!paths.some(a=>a!==p&&a.endsWith('/')&&p.startsWith(a)));
}
