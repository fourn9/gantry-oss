import {meshFile} from './studio_model.js?v=spatial-20261108';
const matches=(path,p)=>path===p||(p.endsWith('/')&&path.startsWith(p));
// Saved mappings only: never infer a physical location from a filename or agent text.
export function spatialPaths(saved,path,nodeId){
 const nodes=saved.state.hierarchy||[],manifest=saved.manifest;
 if(path&&meshFile(path))return manifest[path]?[path]:[];
 const linked=path?nodes.filter(n=>(n.paths||[]).some(p=>matches(path,p))):nodes.filter(n=>n.id===nodeId);
 return [...new Set(linked.flatMap(n=>[...(n.spatial_paths||[]),...(!path?Object.keys(manifest).filter(p=>(n.paths||[]).some(prefix=>matches(p,prefix))):[])]))].filter(p=>manifest[p]&&meshFile(p));
}
export function artifactKind(path){
 if(meshFile(path))return 'Mesh';
 if(/\.(urdf|mjcf)$/i.test(path))return 'Robot model';
 if(/\.(yaml|yml|json|toml)$/i.test(path))return 'Configuration';
 if(/\.(csv|tsv)$/i.test(path))return 'Measurements';
 if(/\.(step|stp|catpart|sldprt)$/i.test(path))return 'CAD source';
 if(/\.(py|cpp|c|h|rs|ino|js|ts)$/i.test(path))return 'Code';
 return 'File';
}
export function workFiles(saved){return saved.diffs?.length?saved.diffs:Object.keys(saved.manifest).map(path=>({path,kind:'Baseline'}));}
export function evidenceFiles(saved){return (saved.engineering?.checks||[]).map(c=>({...c,files:Object.entries(c.evidence||{}).map(([path,hash])=>({path,hash,available:saved.manifest[path]?.hash===hash}))}));}
