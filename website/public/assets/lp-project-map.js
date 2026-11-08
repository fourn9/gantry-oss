import {esc} from '../demo/ui.js?v=spatial-20261108';

// An explanatory activity map using the Studio demo's project and work records.
// Movement and messages are illustrative; no agent or external tool is started.
export function mountProjectMap(host, overview, detail){
 if(!host)return;
 const project=overview.projects[0];
 const assembly=project.hierarchy.find(n=>n.id==='wrist');
 const parts=project.hierarchy.filter(n=>n.parent===assembly.id);
 const design=overview.works.find(w=>w.id==='bracket');
 const controls=overview.works.find(w=>w.id==='control');
 const root=host.attachShadow({mode:'open'});
 const passive=parts.filter(n=>!['sensor','control'].includes(n.id));
 root.innerHTML=`<style>
 :host{display:block;color:#28312a;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}.map{padding:22px;background:#fff}.map-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:23px}.map-header h4{font-size:17px;letter-spacing:-.02em;font-weight:500;margin:0 0 4px}.map-header p{font-size:11px;color:#747d72;margin:0}.activity{display:flex;align-items:center;gap:7px;font-size:10px;color:#477657;white-space:nowrap}.dot{width:6px;height:6px;border-radius:50%;background:#4a9764;flex:none}.map-columns,.context-row,.active-map{display:grid;grid-template-columns:38% 62%}.map-columns{border-top:1px solid #e6e9e2;border-bottom:1px solid #e6e9e2;padding:12px 0;font-size:10px;color:#76806f}.phases{display:grid;grid-template-columns:repeat(3,1fr);text-align:center}.phases span{position:relative}.phases span:not(:last-child):after{content:'→';position:absolute;right:-5px;color:#bcc2b7}.phases .current{color:#34714b;font-weight:600}.context-row{align-items:center;padding:10px 0;border-bottom:1px solid #f0f1ed;color:#7d8578;font-size:11px}.context-row span:last-child{font-size:10px;color:#92998b;padding-left:10px}.part{padding:14px 6px 12px 0;height:76px}.part strong{display:block;font-size:12px;font-weight:500;color:#273d2d}.part small{display:block;font-size:9px;letter-spacing:.05em;color:#909888;text-transform:uppercase;margin-top:2px}.part .agent{display:flex;align-items:center;gap:6px;font-size:10px;color:#487454;margin-top:5px;white-space:nowrap}.agent i{width:5px;height:5px;border-radius:50%;background:#579b6a}.active-map{position:relative;padding-top:6px}.lanes{position:relative;min-width:0;height:192px}.lane-svg{position:absolute;inset:0;width:100%;height:192px;overflow:visible}.grid-line{stroke:#eef0ea;stroke-width:1}.route{stroke:#d8dfd2;stroke-width:1.4;fill:none}.flow{stroke:#72a382;stroke-width:2;fill:none}.runner{position:absolute;left:16.6667%;width:13px;height:13px;border:3px solid white;border-radius:50%;background:#4b9566;box-shadow:0 0 0 4px #dfeee2b3;transform:translate(-50%,-50%);transition:left .85s ease-in-out}.join{stroke:#6a9c78;stroke-width:1.5;fill:none;opacity:0;transition:opacity .5s}.lanes.merged .join{opacity:1}.lane-output{position:absolute;bottom:0;width:100%;text-align:center;color:#64816a;font-size:10px;height:20px}.shared{border-top:1px solid #dfe5d9;border-bottom:1px solid #dfe5d9;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 0;margin-top:6px;font-size:11px}.shared strong{font-weight:500}.shared span{color:#788271;font-size:10px}.update{padding-top:16px;min-height:92px}.update strong{display:block;font-size:10px;font-weight:500;color:#50765a;margin-bottom:6px}.update p{margin:0;font-size:12px;line-height:1.6;color:#5e6958}.update.changed{animation:arrive .5s ease-out}@keyframes arrive{from{opacity:.5;transform:translateY(2px)}to{opacity:1;transform:translateY(0)}}:host([data-playing="true"]) .dot{animation:pulse 2s ease-in-out infinite}@keyframes pulse{50%{box-shadow:0 0 0 4px #4a976415}}
 @media(max-width:680px){.map{padding:16px}.map-header{gap:8px}.map-header h4{font-size:16px}.activity{font-size:9px}.map-columns,.context-row,.active-map{grid-template-columns:40% 60%}.part strong{font-size:11px}.part .agent{font-size:9px}.part small{font-size:8px}.context-row{font-size:10px}.context-row span:last-child{font-size:9px}.map-columns{font-size:9px}.shared{font-size:10px}.shared span{font-size:9px}.update{min-height:106px}.update strong{font-size:10px}.update p{font-size:11px}}
 @media(prefers-reduced-motion:reduce){.dot,.update.changed{animation:none!important}.runner,.join{transition:none}}
 </style><div class="map" aria-hidden="true">
 <div class="map-header"><div><h4>${esc(project.name)}</h4><p>${esc(assembly.title)} / Project activity</p></div><span class="activity"><i class="dot"></i><span id="activity-status">Working in parallel</span></span></div>
 <div class="map-columns"><span>Project parts</span><div class="phases"><span>Read</span><span>Change</span><span>Review</span></div></div>
 ${passive.map(n=>`<div class="context-row"><span>${esc(n.title)}</span><span>Outside this change</span></div>`).join('')}
 <div class="active-map"><div><div class="part"><strong>Sensor bracket</strong><small>Hardware</small><span class="agent"><i></i>${esc(design.owner.name)}</span></div><div class="part"><strong>Motion control</strong><small>Software</small><span class="agent"><i></i>${esc(controls.owner.name)}</span></div></div>
 <div class="lanes"><svg class="lane-svg" viewBox="0 0 300 192" preserveAspectRatio="none"><defs><marker id="map-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0 10 5 0 10" fill="none" stroke="#a7b49f" stroke-width="1.5"/></marker></defs>
 <path class="grid-line" d="M50 0V152M150 0V152M250 0V152"/><path class="route" d="M20 38H280" marker-end="url(#map-arrow)"/><path class="route" d="M20 114H280" marker-end="url(#map-arrow)"/>
 <path class="flow" id="flow-a" d="M20 38H50"/><path class="flow" id="flow-b" d="M20 114H50"/>
 <path class="join" d="M250 38V163H150V174M250 114V163"/>
 </svg><i class="runner" style="top:38px"></i><i class="runner" style="top:114px"></i><span class="lane-output" id="lane-output">Same project context</span></div></div>
 <div class="shared"><strong>Gantry / shared history</strong><span id="history-status">Context → both agents</span></div>
 <div class="update"><strong id="note-author"></strong><p id="note-body"></p></div></div>`;
 const steps=[
 {x:50,status:'Working in parallel',output:'Same project context',history:'Context → both agents',author:design.owner.name+' → '+controls.owner.name,note:'Checking bracket clearance. Can you check the controller timing?'},
 {x:150,status:'Working in parallel',output:'Two connected changes',history:'Design + code → history',author:controls.owner.name+' → '+design.owner.name,note:'Proposed wait: 0.25 seconds. The owner needs to confirm the timing tradeoff; motion checks remain open.'},
 {x:250,status:'Decision needed',output:'Timing requirement decision',history:'Changes + reasons recorded',author:design.owner.name+' → you',note:detail.demo_request.question}
 ];
 let index=0,visible=false,timer;const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 function render(){const step=steps[index];
 root.querySelector('#activity-status').textContent=step.status;root.querySelector('#lane-output').textContent=step.output;root.querySelector('#history-status').textContent=step.history;
 root.querySelectorAll('.phases span').forEach((e,i)=>e.classList.toggle('current',i===index));root.querySelector('.lanes').classList.toggle('merged',index===2);
 root.querySelectorAll('.runner').forEach(e=>e.style.left=(step.x/3)+'%');root.querySelector('#flow-a').setAttribute('d',`M20 38H${step.x}`);root.querySelector('#flow-b').setAttribute('d',`M20 114H${step.x}`);
 const note=root.querySelector('.update');note.classList.remove('changed');root.querySelector('#note-author').textContent=step.author;root.querySelector('#note-body').textContent=step.note;requestAnimationFrame(()=>requestAnimationFrame(()=>note.classList.add('changed')));
 host.dataset.step=String(index);host.setAttribute('aria-label',`${project.name}, ${assembly.title}. Base, arm links and gripper are outside this change. ${design.owner.name} works on the sensor bracket; ${controls.owner.name} works on motion control. ${step.status}. ${step.output}. ${step.note} Illustrative demo, not live.`);
 }
 function sync(){clearInterval(timer);const active=visible&&!document.hidden&&!reduced.matches;host.dataset.playing=String(active);if(active)timer=setInterval(()=>{index=(index+1)%steps.length;render();},5000);}
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.2}).observe(host);document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);render();sync();
 host.querySelector('.lp-screen-fallback')?.remove();
}
