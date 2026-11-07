// Pure presentation helpers. Never infer verification or progress from file existence.
export const cadFile = path => /\.(stl|obj|step|stp|catpart|catproduct|sldprt|sldasm|f3d|iges|igs|3mf)$/i.test(path);
export const meshFile = path => /\.(stl|obj)$/i.test(path);
export const codeFile = path => /\.(py|js|mjs|ts|tsx|jsx|c|cc|cpp|h|hpp|rs|go|java|sh|json|yaml|yml|toml|xml|urdf|mjcf|md|txt|ino)$/i.test(path);
export const statusText = work => ({pending:'Queued',running:'In progress',waiting:'Dependency wait',blocked:'Blocked',failed:'Failed',completed:'Completed',cancelled:'Cancelled',paused:'Paused',working:'In progress'}[work.task_status || work.status] || work.task_status || work.status);
export const checkLabel = value => ({unverified:'Not tested',unknown:'Unknown',pass:'Passed',fail:'Failed',running:'Running checks',not_applicable:'Not applicable'}[value] || value);
export const versionLabel = v => `${v.number ? 'v'+v.number : 'Base'} · ${v.sharing==='shared'?'Shared':v.sharing==='baseline'?'Baseline':'Unshared checkpoint'}`;
export function fileChanges(before,after){return [...new Set([...Object.keys(before),...Object.keys(after)])].sort().filter(p=>before[p]?.hash!==after[p]?.hash).map(path=>({path,before:before[path]?.hash,after:after[path]?.hash,kind:!before[path]?'Added':!after[path]?'Deleted':'Modified'}));}
export function linesOf(text){if(!text)return [];const lines=text.split(/\r?\n/);if(lines.at(-1)==='')lines.pop();return lines;}
export function lineDiff(before,after){
  const left=linesOf(before),right=linesOf(after);
  // Bounded LCS for inline review; large files use separate panes with exact line numbers.
  if(left.length*right.length>1000000)return null;
  const rows=Array.from({length:left.length+1},()=>new Uint16Array(right.length+1));
  for(let i=left.length-1;i>=0;i--)for(let j=right.length-1;j>=0;j--)rows[i][j]=left[i]===right[j]?1+rows[i+1][j+1]:Math.max(rows[i+1][j],rows[i][j+1]);
  let i=0,j=0,result=[];
  while(i<left.length||j<right.length){if(i<left.length&&j<right.length&&left[i]===right[j]){result.push({text:right[j],before:++i,after:++j,kind:'same'});}else if(j<right.length&&(i===left.length||rows[i][j+1]>=rows[i+1][j]))result.push({text:right[j],after:++j,kind:'add'});else result.push({text:left[i],before:++i,kind:'remove'});}
  return result;
}
export function relatedWorks(works,projectId,nodeId,nodes=[]){
  const ids=new Set(nodeId?[nodeId]:nodes.map(n=>n.id));let changed=true;
  while(changed){changed=false;for(const n of nodes)if(ids.has(n.parent)&&!ids.has(n.id)){ids.add(n.id);changed=true;}}
  return works.filter(w=>w.project_id===projectId&&(!nodeId||w.components.some(c=>ids.has(c.id))));
}
export function structureLayout(nodes){
  const ids=new Set(nodes.map(n=>n.id)), depths=new Map();
  function depth(node,seen=new Set()){if(depths.has(node.id))return depths.get(node.id);if(!node.parent||!ids.has(node.parent)||seen.has(node.id))return 0;seen.add(node.id);const d=1+depth(nodes.find(n=>n.id===node.parent),seen);depths.set(node.id,d);return d;}
  const levels=[];for(const n of nodes){const d=depth(n);(levels[d] ||= []).push(n);}
  const width=Math.max(650,...levels.map(l=>l.length*220+40)),height=Math.max(330,levels.length*130+60);
  return {width,height,nodes:levels.flatMap((level,d)=>level.map((n,i)=>({...n,x:width*(i+.5)/level.length,y:50+d*130}))) };
}
export function primaryComponents(components){
  const byId=new Map(components.map(c=>[c.id,c])),ancestors=new Set();
  for(const c of components){let parent=c.parent;const seen=new Set([c.id]);while(parent&&!seen.has(parent)){seen.add(parent);ancestors.add(parent);parent=byId.get(parent)?.parent;}}
  return components.filter(c=>!ancestors.has(c.id));
}
export function commentCount(detail,stateId,path,line){
  return (detail.discussion_index||[]).filter(t=>t.state_id===stateId&&t.anchor.path===path&&(line===undefined||t.anchor.line===line)).reduce((n,t)=>n+t.message_count,0);
}

export const libraryURL=(project,node,section,state,anchor,thread,notification)=>'studio/'+encodeURIComponent(project)+'/'+encodeURIComponent(node||'~')+'/'+section+(state?'/'+encodeURIComponent(state):'')+(anchor?'/'+encodeURIComponent(JSON.stringify(anchor)):'')+(thread?'/'+encodeURIComponent(thread):'')+(notification?'/'+encodeURIComponent(notification):'');
export const participantName=(participants,id)=>participants?.find(p=>p.id===id||p.bot_ids?.includes(id))?.name||id;
export const anchorLabel=a=>a.kind==='work'?'Work conversation':a.kind==='project'?'Project conversation':a.kind==='component'?a.component_id:a.kind==='requirement'?a.requirement_id:a.kind==='code'?`${a.path}:${a.line}`:a.path||a.part;
