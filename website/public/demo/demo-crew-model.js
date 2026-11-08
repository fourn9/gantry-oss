// Browser-only sample. No account, runtime, network or persistence adapter exists here.
const sampleSources=[
 {path:'project-brief.md',type:'Project brief',text:'Desktop robot arm: review the sensor bracket and motion controller together. Keep full-motion clearance and physical verification open until checked.'},
 {path:'team-notes.md',type:'Team context',text:'A project lead coordinates planning and review. A design agent owns CAD changes; a controls agent owns motion code. The project owner decides formal adoption.'},
 {path:'work.csv',type:'Task export',text:'Sensor bracket — move inward within cad/. Motion control — review the settling interval within control/. Agree on checks before adopting either change.'}
];
function sampleProposal(){return {
 goal:'Plan a coordinated bracket and controller update for the bench robot.',lead_role_id:'lead',
 roles:[
  {role_id:'lead',name:'project-lead',parent_role_id:null,profile:{mission:'Coordinate the plan and make review needs clear.',responsibilities:['Connect hardware and software work.','Bring unresolved checks to the project owner.']},write_scope:['docs/'],can_assign:true,can_integrate:false,rationale:'The sample team notes call for one planning lead.',evidence_ids:[1]},
  {role_id:'design',name:'design-agent',parent_role_id:'lead',profile:{mission:'Review the sensor bracket and its clearance.',responsibilities:['Prepare the bracket change.','Identify full-motion clearance checks.']},write_scope:['cad/'],can_assign:false,can_integrate:false,rationale:'The sample task export assigns bracket changes to CAD.',evidence_ids:[0,2]},
  {role_id:'controls',name:'controls-agent',parent_role_id:'lead',profile:{mission:'Review motion control alongside the bracket change.',responsibilities:['Review the settling interval.','Coordinate timing checks with the design agent.']},write_scope:['control/'],can_assign:false,can_integrate:false,rationale:'The sample task export pairs motion code with the bracket review.',evidence_ids:[0,2]}
 ],
 first_task:{id:'sample-planning-task',title:'Plan the bracket and controller update',completion:['Agree on responsibilities and editable paths.','Record the remaining motion and physical checks.']}
};}
const initial=()=>({status:'sources',sources:[],proposal:null,version:0,preparedVersion:null,firstTask:null});
const bounded=(value,label,max,required=true)=>{if(typeof value!=='string'||value.length>max)throw new Error(`${label} must be ${max} characters or fewer.`);const text=value.trim();if(required&&!text)throw new Error(`${label} is required.`);return text;};

// Adapted from the product crew_setup_model editRole pattern; sample-only validation.
function editRole(proposal,index,values){
 const p=structuredClone(proposal),r=p.roles[index];if(!r)throw new Error('Role no longer exists. Reset the demo.');
 r.name=bounded(values.name,'Name',80);r.parent_role_id=bounded(values.parent,'Reporting role',80,false)||null;
 r.profile.mission=bounded(values.mission,'Mission',400);
 r.profile.responsibilities=bounded(values.responsibilities,'Responsibilities',2000).split('\n').map(x=>x.trim()).filter(Boolean);
 r.write_scope=bounded(values.scope,'Editable paths',1000,false).split('\n').map(x=>x.trim()).filter(Boolean);
 r.can_assign=Boolean(values.assign);r.can_integrate=Boolean(values.integrate);
 if(r.write_scope.some(path=>!/^[-\w]+(?:\/[\w.-]+)*\/?$/.test(path)||path.split('/').some(x=>x==='.'||x==='..')))throw new Error('Use relative editable paths such as cad/ or control/.');
 if(p.roles.find(x=>x.role_id===p.lead_role_id).parent_role_id!==null)throw new Error('The lead reports to the project owner.');
 for(const role of p.roles){
  if(role.role_id!==p.lead_role_id&&!p.roles.some(x=>x.role_id===role.parent_role_id))throw new Error('Each role must report to another team role.');
  const seen=new Set();let current=role;
  while(current){if(seen.has(current.role_id))throw new Error('Reporting relationships cannot form a cycle.');seen.add(current.role_id);current=p.roles.find(x=>x.role_id===current.parent_role_id);}
 }
 return p;
}

export function createDemoCrew(){
 let state=initial();
 const requireReview=()=>{if(state.status!=='review')throw new Error(state.proposal?'The team is already created. Reset the demo to review a new team.':'Load the sample sources and suggest a team first.');};
 return {
  snapshot:()=>structuredClone(state),
  reset:()=>{state=initial();},
  loadSources:()=>{if(state.status!=='sources')throw new Error('Reset the demo to choose new sources.');state.sources=structuredClone(sampleSources);},
  suggest:()=>{if(state.status!=='sources'||!state.sources.length)throw new Error('Load the sample sources first.');state.proposal=sampleProposal();state.version=1;state.status='review';},
  saveRole:(index,values)=>{requireReview();const next=editRole(state.proposal,index,values);state.proposal=next;state.version++;state.preparedVersion=null;},
  prepare:()=>{requireReview();state.preparedVersion=state.version;},
  create:()=>{requireReview();if(state.preparedVersion!==state.version)throw new Error('Prepare this reviewed proposal before creating the team.');state.status='ready';},
  start:()=>{if(!['ready','running','stopped'].includes(state.status))throw new Error('Create the team before starting the sample.');state.firstTask??=structuredClone(state.proposal.first_task);state.status='running';},
  stop:()=>{if(state.status!=='running')throw new Error('Start the sample before stopping it.');state.status='stopped';}
 };
}
