"""Bounded inventory-derived suggestions; no model claims or project execution."""
from pathlib import PurePosixPath
from .model import digest

CAD={'.step','.stp','.sldprt','.sldasm','.catpart','.catproduct','.fcstd','.3dxml','.ipt','.iam','.f3d'}
CODE={'.py','.rs','.c','.cpp','.h','.hpp','.js','.ts','.toml','.yaml','.yml'}
ECAD={'.kicad_pcb','.kicad_sch','.pcbdoc','.schdoc','.brd','.dsn'}

def category(path):
    ext=PurePosixPath(path).suffix.lower()
    if ext in CAD:return 'CAD source'
    if ext in ECAD:return 'Electrical source'
    if ext in {'.stl','.obj','.glb'}:return 'Geometry preview'
    if ext in CODE:return 'Code / configuration'
    return 'Saved file'

def evidence(paths,manifest):return [{'path':p,'hash':manifest[p]['hash']} for p in sorted(paths)]

def discover(manifest,name):
    paths=sorted(manifest);groups={}
    for path in paths:
        parent=str(PurePosixPath(path).parent)
        groups.setdefault(parent,[]).append(path)
    nodes=[{'id':'project','title':name,'kind':'project','paths':paths,'editable':True}]
    for folder,files in [(k,v) for k,v in sorted(groups.items()) if k!='.'][:99]:
        if folder=='.':continue
        nodes.append({'id':'folder-'+digest(folder)[:16], 'parent':'project','title':folder,
                      'kind':'inferred component','paths':files,'editable':True})
    questions=[]
    for folder,files in sorted(groups.items()):
        candidates=[p for p in files if PurePosixPath(p).suffix.lower() in CAD]
        if len(candidates)<2:continue
        questions.append({'id':'cad-use-'+digest(folder)[:16],
            'text':f'How do the CAD sources in {folder} relate to the work you want to share?',
            'why':'Their presence does not identify the current assembly or whether they are separate parts.',
            'options':['Different parts / uses','Not sure yet'], 'evidence':evidence(candidates,manifest)})
    return {'method':'file-inventory-v1','hierarchy':nodes,'questions':questions[:20],
        'facts':[{'path':p,'hash':manifest[p]['hash'],'size':manifest[p]['size'],
                  'category':category(p),'status':'observed'} for p in paths],
        'limitations':['Folder grouping is inferred; it is not an engineering decomposition.',
            'Native CAD features, electrical connections and cross-tool dependencies have not been interpreted.',
            'Saved files do not establish the latest external version, test success or environment readiness.']+
            (['Only the first 99 folders are grouped; all selected files remain in the root and source manifest.'] if len([k for k in groups if k!='.'])>99 else [])}
