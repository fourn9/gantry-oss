"""Native generation input/output bindings for adapter preflight.

A binding records an observed pairing. Hash equality alone is not proof that a
CAD generator produced it correctly, or that a dependency inventory is complete.
Keep receipts in immutable Gantry artifacts and verify before invoking a recipe.
"""
import hashlib
from pathlib import Path
from .model import require,digest


def file_hash(root,name):
    root=Path(root).resolve()
    require(isinstance(name,str) and name and not Path(name).is_absolute() and '..' not in Path(name).parts,
            'invalid_input','Generation paths must be workspace-relative')
    path=root/name
    require(path.resolve().is_relative_to(root) and not path.is_symlink(),'invalid_input','Generation path escapes workspace')
    if not path.is_file():return None
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def bind_generation(root,inputs,outputs,*,method,evidence):
    require(inputs and outputs and method and evidence,'invalid_input','Inputs, outputs and evidence are required')
    groups={key:{p:file_hash(root,p) for p in sorted(set(paths))}
            for key,paths in [('inputs',inputs),('outputs',outputs)]}
    require(all(v is not None for group in groups.values() for v in group.values()),'not_found','Generation file missing')
    return {'schema':'gantry.generation-binding.v1',**groups,'method':method,'evidence':evidence,
            'classification':'declared','coverage':'adapter-selected inputs and outputs; completeness not proven',
            'adoption':'unadopted'}


def check_generation(root,receipt):
    require(receipt.get('schema')=='gantry.generation-binding.v1','invalid_input','Unknown generation binding')
    differences=[]
    for group in ('inputs','outputs'):
        require(isinstance(receipt.get(group),dict) and receipt[group],'invalid_input','Nonempty generation file groups required')
        for name,expected in receipt[group].items():
            require(isinstance(expected,str) and len(expected)==64 and all(c in '0123456789abcdef' for c in expected),
                    'invalid_input','SHA-256 binding required')
            actual=file_hash(root,name)
            if actual!=expected:differences.append({'role':group,'path':name,'expected':expected,'actual':actual,
                                                    'reason':'missing' if actual is None else 'changed'})
    return {'schema':'gantry.generation-check.v1','binding_digest':digest(receipt),'differences':differences,
            'status':'needs_regeneration_or_review' if differences else 'bound_files_match',
            'ready_for_bound_recipe':not differences,'verification':'unverified','adoption':'unadopted',
            'scope':'File identity only; fresh generation/alignment evidence required to rebind changed sources'}
