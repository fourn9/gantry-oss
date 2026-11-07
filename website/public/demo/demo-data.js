// Public, invented sample data. This adapter never opens a network connection.
import {createLibraryFixture} from './demo-library.js?v=library-20261107';
import {fileChanges} from './studio_model.js?v=library-20261107';
import {componentScope} from './studio_context.js?v=library-20261107';
const clone=value=>structuredClone(value);
const members=[{id:'designer',name:'Alex Morgan',role:'Project owner',kind:'human'},{id:'controls-agent',name:'Kai',role:'Controls Crew agent',kind:'agent'},{id:'design-agent',name:'Ari',role:'Mechanical Crew agent',kind:'agent'},{id:'mechanical-reviewer',name:'Sam Rivera',role:'Mechanical reviewer',kind:'human'}];
const hierarchy=[
 {id:'robot',title:'Bench robot',kind:'robot',paths:['cad/','control/']},
 {id:'wrist',parent:'robot',title:'Wrist assembly',kind:'assembly',paths:['cad/','control/']},
 {id:'frame',parent:'wrist',title:'Frame',kind:'mechanical',paths:['cad/base.stl']},
 {id:'carriage',parent:'wrist',title:'Carriage',kind:'mechanical',paths:['cad/carriage.stl']},
 {id:'sensor',parent:'wrist',title:'Sensor bracket',kind:'mechanical',paths:['cad/sensor-bracket.stl']},
 {id:'control',parent:'wrist',title:'Motion control',kind:'software',paths:['control/']}];
const box=(x,y,z,dx,dy,dz)=>{
 const points=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]].map(([i,j,k])=>[x+i*dx,y+j*dy,z+k*dz]);
 return [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]].map(f=>'facet normal 0 0 0\nouter loop\n'+f.map(i=>'vertex '+points[i].join(' ')+'\n').join('')+'endloop\nendfacet\n').join('');
};
const mesh=body=>'solid sample\n'+body+'endsolid sample\n';
const bracket=x=>mesh(box(x,-30,28,8,60,5)+box(x,25,28,8,5,26));
const code=settle=>`# Illustrative control code. Not connected to a robot.\nSETTLE_TIME = ${settle}\n\ndef move_axis(axis, target):\n    axis.move_to(target)\n    axis.wait(SETTLE_TIME)\n    return axis.position()\n`;
const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
const canonical=a=>JSON.stringify(Object.entries(a).sort());

export async function createDemoAPI(){
 let states,works,threads,inbox,blobs,seq,counter;
 const must=(value,message)=>{if(!value)throw new Error(message);return value;};
 const text=(value,max)=>must(typeof value==='string'&&value.length<=max,'Text exceeds the demo limit.');
 const state=id=>must(states[id],'This sample version is unavailable.');
 const work=id=>must(works[id],'This sample work is unavailable.');
 const library=createLibraryFixture({state,getStates:()=>states,getWorks:()=>works,getThreads:()=>threads,members,hierarchy,getSeq:()=>seq});
 async function saveState(id,files,summary,sharing='local',previous=null){
  const manifest={};for(const [path,content] of Object.entries(files)){
   const bytes=new TextEncoder().encode(content),hash=await digest(bytes);
   blobs[hash]={content:btoa(String.fromCharCode(...bytes)),hash};manifest[path]={hash,size:bytes.length};
  }
  const value={state:{id,snapshot:id,summary,session_id:'sample-session',hierarchy:clone(hierarchy),parents:previous?[previous.state.id]:[],created_at:Date.UTC(2026,10,1,8)+counter*1000,capture:{missing:['Native CAD source','Real test execution','Live agents and external tools']},unfinished:['Verify full-motion clearance','Resolve and measure controller settling time']},manifest,
   status:{work:'working',sharing,verification:id==='state_base'?'pass':'unverified',adoption:'unadopted'},
   diffs:previous?fileChanges(previous.manifest,manifest):[],engineering:{checks:[{id:'Full-motion clearance',scope:'Sample assembly · physical verification required',effective_status:'unverified'}]},
   evaluations:[{state_id:'state_base',scope:'Sample result · controller syntax (illustrative, not executed)',verdict:'pass',applicable:id==='state_base'}],files};
  states[id]=value;return value;
 }
 function detail(wid,sid){
  const w=work(wid),id=sid||w.head;must(w.versions.includes(id),'Version does not belong to this work.');
  const versions=w.versions.map((id,number)=>({id,number,sharing:state(id).status.sharing,notes:state(id).notes||[]}));
  const selected=clone(state(id));delete selected.files;
  return {work:clone(w),selected,versions,threads:clone(threads.filter(t=>t.work_id===wid&&t.state_id===id)),
   discussion_index:threads.filter(t=>t.work_id===wid).map(t=>({...clone(t),message_count:t.messages.length})),
   participants:clone(members),can_update:true,can_comment:true,source:{repository:'sample/bench-robot',commit:''},
   capture:{missing:['Native CAD source','Real test execution','Live agents and external tools']},activity:[],activity_token:String(seq),
   demo_request:wid==='bracket'&&id==='state_bracket_v1'?{agent:'design-agent',agent_name:'Ari',thread_id:'thread_sample',state_id:id,anchor:clone(threads.find(t=>t.id==='thread_sample').anchor),
    reason:'The proposed controller wait exceeds the current 0.15-second requirement. Changing that requirement needs the project owner’s direction.',
    changed:'Bracket moved inward by 2 mesh units. Controller wait: 0.15 → 0.25 seconds (+0.10 seconds per move).',
    remaining:'After your direction, the team can evaluate motion clearance and timing. Neither has been verified for this update. This demo records replies only; it does not run checks.',
    summary:'Adds 0.10 seconds per move; exceeds the current timing requirement.',
    question:'Can settling time increase to 0.25 seconds?',
    replied:threads.find(t=>t.id==='thread_sample').messages.some(m=>m.author==='designer')}:null};
 }
 async function reset(){
  states=Object.create(null);works=Object.create(null);blobs=Object.create(null);threads=[];inbox=[];seq=1;counter=1;
  const files={'cad/base.stl':mesh(box(-60,-40,0,120,80,6)+box(-50,-30,6,8,60,40)+box(42,-30,6,8,60,40)),
   'cad/carriage.stl':mesh(box(-36,-22,20,72,44,8)+box(-30,-16,28,60,32,18)),
   'cad/sensor-bracket.stl':bracket(26),'control/motion.py':code('0.15')};
  await saveState('state_base',files,'Sample baseline. Geometry and results are illustrative.','baseline');
  await saveState('state_bracket_v1',{...files,'cad/sensor-bracket.stl':bracket(24),'control/motion.py':code('0.25')},'Moved bracket inward and increased settling time; motion checks pending.','shared',state('state_base'));
  for(const [id,title,owner,components,purpose,head,status] of [
   ['bracket','Refine the sensor bracket','design-agent',['sensor','control'],'Resolve the timing requirement before evaluating the proposed change.','state_bracket_v1','working'],
   ['control','Adjust the settling interval','controls-agent',['control'],'Coordinate the controller with the assembly.','state_base','waiting'],
   ['access','Review service access','mechanical-reviewer',['frame','carriage'],'Check access before detailing fasteners.','state_base','working']]){
    works[id]={id,title,owner:clone(members.find(m=>m.id===owner)),components:hierarchy.filter(n=>components.includes(n.id)),project_id:'bench',purpose,head,status,
     waiting_reason:id==='control'?'Timing requirement decision':'',waiting_on:id==='control'?{work_id:'bracket',state_id:'state_bracket_v1',thread_id:'thread_sample'}:null,write_scope:components.flatMap(id=>hierarchy.find(n=>n.id===id).paths),sharing:state(head).status.sharing,version:1,session_id:'sample-session',versions:head==='state_base'?['state_base']:['state_base',head]};
  }
  const anchor={kind:'code',path:'control/motion.py',line:2,hash:state('state_bracket_v1').manifest['control/motion.py'].hash};
  const related_anchor={kind:'cad',path:'cad/sensor-bracket.stl',part:'cad/sensor-bracket.stl',hash:state('state_bracket_v1').manifest['cad/sensor-bracket.stl'].hash};
  threads.push({id:'thread_sample',work_id:'bracket',state_id:'state_bracket_v1',anchor,compare_state_id:'state_base',related_anchor,messages:[
   {author:'design-agent',at:Date.UTC(2026,10,1,8,50),body:'@Kai I am moving the bracket inward. Check the controller timing alongside this change.',mentions:['controls-agent']},
   {author:'controls-agent',at:Date.UTC(2026,10,1,8,55),body:'@Ari I propose 0.25 seconds to settle. That is 0.10 seconds above the current requirement; the owner needs to confirm the timing tradeoff before we evaluate this candidate.',mentions:['design-agent']},
   {author:'design-agent',at:Date.UTC(2026,10,1,9),body:'@Alex Morgan Can settling time increase from 0.15 to 0.25 seconds? This adds 0.10 seconds per move. Confirm the timing tradeoff, or ask us to revise within the current limit. Motion and timing checks are still pending.',mentions:['designer']}]});
  inbox.push({id:'request_sample',work_id:'bracket',state_id:'state_bracket_v1',thread_id:'thread_sample',anchor,title:'Confirm the settling-time requirement',author:'design-agent',body:threads[0].messages.at(-1).body,read:false,kind:'Change review',project_id:'bench',project_name:'Bench robot',scope:'Sensor bracket + Motion control',contributors:['design-agent','controls-agent'],contributor_names:['Ari','Kai']});
  const requirementAnchor={kind:'requirement',requirement_id:'settling-time',revision_id:'timing-r1'};
  threads.push({id:'thread_requirement_sample',project_id:'bench',state_id:'state_base',anchor:requirementAnchor,messages:[{id:'message_requirement_sample',author:'controls-agent',at:Date.UTC(2026,10,1,8,30),body:'@Alex Morgan The saved requirement is 0.15 seconds. A measured timing report is still missing. Confirm which evidence the team should acquire before any requirement change.',mentions:['designer']}]});
  inbox.push({id:'request_requirement_sample',project_id:'bench',state_id:'state_base',thread_id:'thread_requirement_sample',anchor:requirementAnchor,title:'Review the timing requirement',author:'controls-agent',body:threads.at(-1).messages[0].body,read:false,kind:'Requirement discussion'});

 }
 async function api(command,args={}){
  switch(command){
   case 'studio_library':return clone(library.library(args));
   case 'studio_related':return library.related(args);
   case 'studio_context':return clone(library.context(args));
   case 'studio_overview':return clone({projects:[{id:'bench',name:'Bench robot',hierarchy,structure_state:'state_base'}],works:Object.values(works),next:null,collaboration:{work_id:'bracket',state_id:'state_bracket_v1',thread_id:'thread_sample',messages:clone(threads.find(t=>t.id==='thread_sample').messages),replied:threads.find(t=>t.id==='thread_sample').messages.some(m=>m.author==='designer')},activity_token:String(seq)});
   case 'studio_work':return detail(args.work_id,args.state_id);
   case 'get_development_state':{const value=clone(state(args.state_id));delete value.files;return value;}
   case 'read_artifact_chunk':{const file=state(args.revision_id).manifest[args.path];must(file&&(!args.index||args.index===0),'Sample artifact not found.');return clone(blobs[file.hash]);}
   case 'demo_import_update':{
    const w=work(args.work_id);must(w.version===args.version,'Work changed. Refresh before importing.');must(counter<25,'Reset the demo to try more updates.');
    const prev=state(w.head),id='state_update_'+(++counter),files={...prev.files};
    const allowed=path=>(w.write_scope||w.components.flatMap(n=>n.paths)).some(p=>path===p||(p.endsWith('/')&&path.startsWith(p)));
    for(const path of Object.keys(files).filter(allowed)){if(path==='control/motion.py')files[path]=code((0.25+counter*.025).toFixed(2));else if(path==='cad/sensor-bracket.stl')files[path]=bracket(24-counter);else files[path]=files[path].replace(/vertex (-?[\d.]+)/g,(_,x)=>'vertex '+(Number(x)+0.5));}
    await saveState(id,files,'Sample saved edit · verification pending','local',prev);w.head=id;w.sharing='local';w.versions.push(id);w.version++;seq++;
    return {state:{id}};
   }
   case 'studio_share_update':{
    const w=work(args.work_id);must(w.version===args.version&&w.head===args.state_id,'Work changed. Refresh before sharing.');text(args.note||'',1000);
    const v=state(w.head);must(v.status.sharing==='local','Only an unshared sample checkpoint can be shared.');
    v.status.sharing='shared';v.notes=[args.note||''];w.sharing='shared';w.version++;seq++;return {state_id:w.head};
   }
   case 'studio_comment':{
    const w=args.work_id?work(args.work_id):null;if(w)must(w.versions.includes(args.state_id),'Version does not belong to this work.');
    library.validate({...args,project_id:args.project_id||w?.project_id});
    text(args.body,4000);must(args.body.trim(),'Write a comment first.');must(threads.reduce((n,t)=>n+t.messages.length,0)<100,'Reset the demo to add more comments.');
    const anchor=args.anchor;
    const mentions=args.mentions||[];must(Array.isArray(mentions)&&mentions.every(id=>members.some(m=>m.id===id)),'Unknown sample participant.');
    let t=threads.find(t=>(w?t.work_id===w.id:!t.work_id&&t.project_id===args.project_id)&&t.state_id===args.state_id&&canonical(t.anchor)===canonical(anchor));
    if(args.thread_id)must(t?.id===args.thread_id,'Replies must keep their original saved target.');
    if(!t){t={id:'thread_'+(++counter),...(w?{work_id:w.id}:{project_id:args.project_id}),state_id:args.state_id,anchor:clone(anchor),messages:[]};threads.push(t);}
    t.messages.push({id:'message_'+(++counter),author:'designer',at:Date.now(),body:args.body,mentions:clone(mentions)});
    for(const recipient of mentions)inbox.unshift({id:'request_'+(++counter),recipient,...(w?{work_id:w.id}:{project_id:args.project_id}),state_id:args.state_id,thread_id:t.id,anchor:clone(anchor),title:w?.title||({project:'Project conversation',component:'Component conversation',requirement:'Requirement conversation'}[anchor.kind]||anchor.path),author:'designer',body:args.body,read:false});
    seq++;return {thread_id:t.id};
   }
   case 'studio_inbox':return clone({items:inbox.filter(i=>!i.recipient||i.recipient==='designer').map(i=>({...i,author_name:members.find(p=>p.id===i.author)?.name||i.author,reply_sent:threads.find(t=>t.id===i.thread_id)?.messages.some(m=>m.author==='designer')||false})),next:null,activity_token:String(seq)});
   case 'studio_acknowledge':{const item=inbox.find(i=>i.id===args.notification_id);must(item,'Request not found.');item.read=true;seq++;return {};}
   case 'session_details':return {session:{owner:'designer',actors:members.map(m=>m.id)},participants:clone(members)};
   case 'begin_change':{
    text(args.title,240);text(args.purpose,1000);must(args.title.trim()&&args.purpose.trim(),'Add a title and purpose.');state(args.state_id);
    const owner=must(members.find(m=>m.id===args.assignee),'Choose a sample participant.');must(Object.keys(works).length<15,'Reset the demo to add more work.');
    const selected=hierarchy.find(n=>n.id===args.component_id);
    if(args.component_id)must(selected,'Choose a known component.');
    const scope=componentScope(hierarchy,selected?.id||'robot',(args.write_scope||[]).join('\n'));
    const id='work_'+(++counter);works[id]={id,title:args.title,purpose:args.purpose,owner:clone(owner),project_id:'bench',head:args.state_id,versions:[args.state_id],version:1,sharing:state(args.state_id).status.sharing,status:'working',session_id:'sample-session',write_scope:scope,components:selected?[clone(selected)]:hierarchy.filter(n=>n.id!=='robot'&&n.id!=='wrist'&&n.paths.some(p=>scope.some(s=>p===s||(s.endsWith('/')&&p.startsWith(s)))))};
    seq++;return {id};
   }
   default:throw new Error('This action requires a connected Gantry workspace. The public demo has no backend connection.');
  }
 }
 await reset();return {api,reset};
}
