// Invented, in-memory read models. No network, tool execution or inferred evidence.
import {fileChanges,linesOf} from './studio_model.js?v=component-20261107';
const clone=value=>structuredClone(value);
const same=(a,b)=>JSON.stringify(Object.entries(a).sort())===JSON.stringify(Object.entries(b).sort());
const must=(v,message)=>{if(!v)throw new Error(message);return v;};
const inScope=(path,paths)=>paths.some(p=>path===p||(p.endsWith('/')&&path.startsWith(p)));
export function createLibraryFixture({state,getStates,getWorks,getThreads,members,hierarchy,getSeq}){
 const project={id:'bench',name:'Desktop robot arm'};
 function saved(args){must(args.project_id==='bench','Unknown sample project.');return state(args.state_id||'state_base');}
 function meta(v){return {...clone(v.state),sharing:v.status.sharing,adoption:v.status.adoption};}
 function scope(id){const node=must(hierarchy.find(n=>n.id===id),'Unknown sample component.');const ids=new Set([node.id]);for(const _ of hierarchy)for(const n of hierarchy)if(ids.has(n.parent))ids.add(n.id);return hierarchy.filter(n=>ids.has(n.id)).flatMap(n=>n.paths);}
 function coverage(v){
  const changed=v.manifest['control/motion.py'].hash!==state('state_base').manifest['control/motion.py'].hash;
  return [
   {requirement_id:'settling-time',revision_id:'timing-r1',description:'Controller settling time must stay at or below 0.15 seconds.',status:'unverified',checks:[{check_id:'timing-check',status:'unverified',reason:'not_linked_or_missing',stale_inputs:changed?['control/motion.py']:[],stale_evidence:[]}],gaps:['A measured timing report is still required.']},
   {requirement_id:'motion-clearance',revision_id:'clearance-r1',description:'The wrist must clear the sensor bracket throughout full motion.',status:'unverified',checks:[{check_id:'clearance-check',status:'unverified',reason:'not_linked_or_missing',stale_inputs:[],stale_evidence:[]}],gaps:['Full-motion clearance has not been physically verified.']}
  ];
 }
 function checks(v){return [
  {id:'timing-check',inputs:['control/motion.py'],evidence:{},requirement_refs:[{requirement_id:'settling-time',revision_id:'timing-r1'}],effective_status:'unverified'},
  {id:'clearance-check',inputs:['cad/sensor-bracket.stl','cad/arm-links.stl'],evidence:{},requirement_refs:[{requirement_id:'motion-clearance',revision_id:'clearance-r1'}],effective_status:'unverified'}
 ];}
 function validate(args){
  const v=saved(args),a=args.anchor;
  must(a&&['project','component','requirement','file','cad','code','work'].includes(a.kind),'Unsupported comment target.');
  const fields={project:['kind'],work:['kind'],component:['kind','component_id'],requirement:['kind','requirement_id','revision_id'],file:['kind','path','hash'],cad:['kind','path','hash','part'],code:['kind','path','hash','line']}[a.kind];
  must(Object.keys(a).length===fields.length&&fields.every(k=>Object.hasOwn(a,k)),'Invalid saved target.');
  if(a.kind==='component')scope(a.component_id);
  if(a.kind==='requirement')must(coverage(v).some(r=>r.requirement_id===a.requirement_id&&r.revision_id===a.revision_id),'Requirement revision is not pinned in this state.');
  if(a.path){const f=v.manifest[a.path];must(f&&f.hash===a.hash,'The selected file version changed.');
   if(a.kind==='cad')must(a.part===a.path&&/\.(stl|obj)$/i.test(a.path),'Select a saved mesh part.');
   if(a.kind==='code')must(Number.isInteger(a.line)&&a.line>0&&a.line<=linesOf(v.files[a.path]).length,'Select an existing line.');
  }
  must(a.kind!=='work'||args.work_id,'A work conversation needs its work record.');return v;
 }
 function page(items,args,key){const limit=args.limit??50;must(Number.isInteger(limit)&&limit>=1&&limit<=100,'Invalid page limit.');const rows=items.filter(x=>x[key]>(args.after||'')).sort((a,b)=>a[key]<b[key]?-1:1);return {items:clone(rows.slice(0,limit)),next:rows.length>limit?rows[limit-1][key]:null};}
 function library(args){
  const v=saved(args),paths=args.component_id?scope(args.component_id):null,query=(args.query||'').toLowerCase();
  const common={project,state:meta(v),section:args.section,baseline_state:'state_base',source:{state_id:v.state.id,snapshot:v.state.snapshot}};
  if(args.section==='versions')return {...common,...page(Object.values(getStates()).map(meta),args,'id')};
  if(args.section==='files')return {...common,...page(Object.entries(v.manifest).filter(([p])=>(!paths||inScope(p,paths))&&p.toLowerCase().includes(query)&&(!args.path||p===args.path)).map(([path,f])=>({path,...f,storage:'bytes_saved',components:hierarchy.filter(n=>inScope(path,n.paths)).map(n=>n.id)})),args,'path'),components:[]};
  must(args.section==='requirements','Unknown library section.');
  const ids=checks(v).filter(c=>!paths||c.inputs.some(p=>inScope(p,paths))).flatMap(c=>c.requirement_refs.map(r=>r.requirement_id));
  return {...common,...page(coverage(v).filter(r=>ids.includes(r.requirement_id)&&(r.description+' '+r.requirement_id).toLowerCase().includes(query)),args,'requirement_id'),unlinked_requirements:['Prefer easy service access; no verification link recorded.'],limitations:['Illustrative requirements; no checks were executed.']};
 }
 function related(args){
  const v=validate(args),a=args.anchor;
  const paths=a.path?[a.path]:a.kind==='component'?Object.keys(v.manifest).filter(p=>inScope(p,scope(a.component_id))):[];
  const linked=checks(v).filter(c=>a.kind==='requirement'?c.requirement_refs.some(r=>r.requirement_id===a.requirement_id):['project','work'].includes(a.kind)||c.inputs.some(p=>paths.includes(p)));
  const ids=linked.flatMap(c=>c.requirement_refs.map(r=>r.requirement_id)),allPaths=[...new Set([...paths,...linked.flatMap(c=>c.inputs)])].sort();
  const works=Object.values(getWorks()).filter(w=>w.versions.includes(v.state.id)&&(['project','work'].includes(a.kind)||allPaths.some(p=>inScope(p,w.write_scope)))).map(w=>({...clone(w),relation:w.versions[0]===v.state.id?'starts_from_state':'contains_checkpoint'}));
  const workPage=page(works,args,'id');
  const threads=getThreads().filter(t=>!t.work_id&&t.project_id==='bench'&&t.state_id===v.state.id&&same(t.anchor,a));
  const messages=threads.flatMap(t=>t.messages).sort((a,b)=>b.at-a.at||b.id.localeCompare(a.id));
  const offset=args.message_after?messages.findIndex(m=>m.id===args.message_after)+1:0;must(!args.message_after||offset>0,'Invalid message cursor.');
  const visible=messages.slice(offset,offset+(args.limit??50)),visibleIds=new Set(visible.map(m=>m.id));
  return clone({state:meta(v),anchor:a,requirements:coverage(v).filter(r=>ids.includes(r.requirement_id)),checks:linked,checks_truncated:false,files:allPaths.map(path=>({path,...v.manifest[path]})),files_truncated:false,works:workPage.items,next:workPage.next,
   relation_basis:'Explicit requirement references and declared check inputs; not inferred fulfillment.',limitations:['Illustrative saved data; no real verification.'],participants:members,session_version:1,write_scope:['cad/','control/'],can_comment:true,can_ask_bot:false,can_assign_bot:false,bot_requests:[],activity_token:String(getSeq()),
   threads:threads.map(t=>({...t,messages:t.messages.filter(m=>visibleIds.has(m.id))})),message_next:messages.length>offset+visible.length?visible.at(-1).id:null});
 }
 function context(args){
  const v=validate(args),r=related(args);let delta=null;
  if(args.since_state){const old=state(args.since_state);delta={from_state:old.state.id,to_state:v.state.id,...page(fileChanges(old.manifest,v.manifest).map(f=>({path:f.path})),{...args,after:args.delta_after},'path'),context_changed:old.state.id!==v.state.id};}
  return {source:{project_id:'bench',state_id:v.state.id,snapshot:v.state.snapshot,ledger_seq:getSeq()},mandatory:{requirements:coverage(v),unlinked_requirements:['Prefer easy service access; no verification link recorded.'],constraints:['Keep settling time at or below 0.15 seconds until the owner changes the requirement.','Sharing or replying does not verify or adopt a design.'],open_questions:['Can settling time increase to 0.25 seconds?'],unfinished:v.state.unfinished,capture:v.state.capture},related:r,delta,retrieval:{files:'studio_library',related:'studio_related',bytes:'read_artifact_chunk',versions:'studio_library (section=versions)'},limitations:['In-memory sample only. No model is called.','No file bodies included. Retrieve exact saved bytes separately.']};
 }
 return {validate,library,related,context};
}
