"""Customer-local declarative CAD edits. No Python recipe execution or cloud calls."""
import hashlib
import math
import re
import shutil
import tempfile
from pathlib import Path
from .model import require, canonical, digest


def number(value, positive=False):
    require(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e6
            and (not positive or value > 0), 'invalid_input', 'Bounded finite dimension required')
    return value


def source(root, name, sha256):
    require(isinstance(name, str), 'invalid_input', 'Relative input path required')
    rel = Path(name); path = Path(root) / rel
    require(not rel.is_absolute() and '..' not in rel.parts and rel.parts
            and not any((Path(root)/Path(*rel.parts[:i])).is_symlink() for i in range(1,len(rel.parts)+1))
            and path.is_file() and path.resolve().is_relative_to(Path(root).resolve()),
            'scope_denied', 'Regular input within workspace required')
    require(path.stat().st_size <= 100*1024**2, 'invalid_input', 'Input exceeds 100 MiB')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == sha256, 'stale_basis', 'Input hash differs')
    return raw


def edit(root, request, destination):
    from . import cad_kernel as kernel
    root = Path(root).resolve(); destination = Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink(), 'conflict', 'Use a new output directory')
    require(isinstance(request, dict) and set(request) == {'unit','frame','steps','export'}
            and request['unit']=='mm' and isinstance(request['frame'],str) and request['frame'],
            'invalid_input', 'Explicit mm unit, frame, steps and export required')
    steps, exports = request['steps'], request['export']
    require(isinstance(steps,list) and 1<=len(steps)<=100 and isinstance(exports,list)
            and 1<=len(exports)<=100 and all(isinstance(x,str) for x in exports)
            and len(set(exports))==len(exports), 'invalid_input', 'Bounded steps/exports required')
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.gantry-cad-',dir=destination.parent))
    shapes={}; history=[]
    fields={'import_step':{'path','sha256'},'box':{'size'},'cylinder':{'radius','height'},
            'translate':{'source','vector'},'cut':{'left','right'},'fuse':{'left','right'}}
    try:
        for step in steps:
            require(isinstance(step,dict) and isinstance(step.get('id'),str)
                    and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',step['id']) and step['id'] not in shapes,
                    'invalid_input','Unique safe shape ID required')
            op=step.get('op'); name=step['id']
            require(isinstance(op,str) and op in fields and set(step)=={'id','op'}|fields[op],
                    'invalid_input','Unsupported CAD operation or fields')
            def shape(key):
                require(isinstance(step[key],str) and step[key] in shapes,'invalid_input','Unknown earlier shape')
                return shapes[step[key]]
            if op=='import_step':
                require(isinstance(step['path'],str) and Path(step['path']).suffix.lower() in {'.step','.stp'},'invalid_input','STEP required')
                raw=source(root,step['path'],step['sha256'])
                input_file=staging/(name+'.input.step'); input_file.write_bytes(raw)
                # Freeze imported bytes before native parsing; never parse a mutable source path.
                result=kernel.import_step(input_file); input_file.unlink()
            elif op=='box':
                size=step['size']
                require(isinstance(size,list) and len(size)==3,'invalid_input','Three dimensions required')
                result=kernel.box(*(number(v,True) for v in size))
            elif op=='cylinder':
                result=kernel.cylinder(number(step['radius'],True),number(step['height'],True))
            elif op=='translate':
                vector=step['vector']
                require(isinstance(vector,list) and len(vector)==3,'invalid_input','Three offsets required')
                result=shape('source').translate(tuple(number(v) for v in vector))
            else:
                left,right=shape('left'),shape('right')
                result=left.cut(right) if op=='cut' else left.fuse(right)
            require(result.isValid() and result.Solids() and math.isfinite(result.Volume()) and result.Volume()>0,
                    'invalid_geometry','Operation did not produce valid positive-volume solids')
            shapes[name]=result; history.append({'step':step,'volume_mm3':result.Volume(),'solids':len(result.Solids())})
        outputs={}
        for name in exports:
            require(name in shapes,'invalid_input','Unknown export ID')
            path=staging/(name+'.step'); kernel.export_step(shapes[name],path)
            outputs[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        report={'adapter':'gantry.cad-io.v1','backend':kernel.BACKEND,
                'request':request,'request_hash':digest(request),'operations':history,'outputs':outputs,
                'limitations':['Solid validity is not design intent or physical fitness',
                    'STEP does not preserve the original parametric feature tree',
                    'Millimeters, one declared common frame; no inferred assembly transforms']}
        (staging/'cad-operation.json').write_text(canonical(report))
        require(not destination.exists() and not destination.is_symlink(),'conflict','Output appeared')
        staging.rename(destination)
        return report
    finally:
        if staging.exists(): shutil.rmtree(staging)
