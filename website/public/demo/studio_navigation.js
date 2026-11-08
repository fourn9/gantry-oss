import {relatedWorks} from './studio_model.js?v=component-20261107';
// Resolve a file to the most specific mapped component, never an unrelated branch.
export function componentForFile(project,path){
 if(!project||!path)return;
 const matches=p=>path===p||(p.endsWith('/')&&path.startsWith(p));
 const specificity=n=>Math.max(...n.paths.filter(matches).map(p=>p.length));
 return project.hierarchy.filter(n=>n.paths?.some(matches)).sort((a,b)=>
  specificity(b)-specificity(a)||Number(project.hierarchy.some(n=>n.parent===a.id))-Number(project.hierarchy.some(n=>n.parent===b.id)))[0];
}
export function componentWork(project,works,id,preferred){
 const choices=relatedWorks(works,project.id,id,project.hierarchy);
 return choices.find(w=>w.id===preferred)||choices.find(w=>w.components?.[0]?.id===id)||choices[0];
}
export function highlightComponent(project,node){
 document.querySelectorAll('.studio-tree-link').forEach(el=>{
  const active=el.dataset.project===project?.id&&el.dataset.component===node?.id;
  el.classList.toggle('is-selected',active);
  if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');
 });
}
