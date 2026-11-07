import {createDemoAPI} from '../demo/demo-data.js?v=library-20261107';
import {esc} from '../demo/ui.js?v=library-20261107';
import {mountProjectMap} from './lp-project-map.js?v=evidence-20261105';
import {requestSummary} from '../demo/studio_views.js?v=library-20261107';
// Present the same renderers and sample data as the working Studio demo.
// Studio excerpts are inert. A clearly labelled, local sample replay adds
// activity summaries; it does not run or connect to live agents.
function mount(id,html){
 const host=document.getElementById(id);
 if(!host)return;
 const root=host.attachShadow({mode:'open'});
 root.innerHTML=`<link rel="stylesheet" href="/demo/style.css?v=library-20261107"><link rel="stylesheet" href="/demo/studio.css?v=library-20261107"><style>
 :host{display:block;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#252724;--bg:#fff;--sidebar:#f7f7f6;--soft:#f6f6f5;--hover:#efefed;--line:#e6e6e3;--text:#252724;--muted:#70746c;--accent:#2b6ddd;--green:#34835d;--red:#ad4c47;--amber:#927236;--radius:7px;--mono:ui-monospace,monospace}
 *{box-sizing:border-box}.excerpt{background:#fff;padding:18px;min-width:0}.studio-request{margin:0;border:0;padding:0;background:#fff}.studio-request-label{display:none}.studio-request h2{font-size:18px;line-height:1.3}.studio-request-main{display:block}.studio-request-main>button{margin-top:12px}.studio-request-details{margin-top:18px}.studio-request-details dl{grid-template-columns:1fr!important;gap:12px}.studio-request-details dd{font-size:12px;line-height:1.55}.studio-request-head{font-size:10px}.studio-request-actions,.studio-request-details>p{display:none}.studio-request-details summary{font-size:11px}.studio-workcolumns,.studio-workgridrow{grid-template-columns:minmax(0,1.2fr) minmax(0,1fr) 56px!important;gap:12px!important}.studio-scope,.studio-workcolumns>span:nth-child(3){display:none}.studio-workgridrow{padding:20px 0!important}.studio-workrow strong{font-size:13px;line-height:1.4}.studio-owner{font-size:11px;overflow-wrap:anywhere}.studio-owner small,.studio-status,.studio-workcolumns{font-size:10px}.excerpt-title{font-size:16px;font-weight:500;margin:0 0 8px}.excerpt-project{font-size:11px;color:#70746c;margin:0 0 20px}.studio-worklist{border:0}button,summary,a{cursor:default}.studio-small{font-size:11px}
 @media(max-width:680px){.excerpt{padding:15px}.studio-workcolumns,.studio-workgridrow{gap:8px!important}.studio-workrow strong{font-size:12px}}

 .sender{display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:18px}.agent-avatar{width:29px;height:29px;display:grid;place-items:center;background:#edf5ed;color:#39764a;border:1px solid #d2e4d4;border-radius:50%;font:11px var(--mono);flex:none}.sender strong{font-size:12px;font-weight:600}.sender small{display:block;color:var(--muted);font-size:10px;margin-top:2px}.sender .sender-tag{margin-left:auto;color:#39764a;font-size:10px;white-space:nowrap}.status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#449363;margin-right:6px;vertical-align:1px}
 </style><div class="excerpt" inert>${html}</div>`;
 root.querySelectorAll('details').forEach(d=>d.open=true);
 host.querySelector('.lp-screen-fallback')?.remove();
 return root;
}
try{
 const {api}=await createDemoAPI();
 const detail=await api('studio_work',{work_id:'bracket'});
 const sender=`<div class="sender"><span class="agent-avatar" aria-hidden="true">D</span><div><strong>${esc(detail.demo_request.agent)} → you</strong><small>Bench robot / Sensor bracket</small></div><span class="sender-tag"><i class="status-dot" aria-hidden="true"></i>Review requested</span></div>`;
 mount('lp-ledger-screen',sender+requestSummary(detail.demo_request));
 const overview=await api('studio_overview');
 mountProjectMap(document.getElementById('lp-crew-screen'),overview,detail);
}catch(error){console.warn('Studio excerpts unavailable; the demo links remain available.',error);}
