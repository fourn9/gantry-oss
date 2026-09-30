"""Version-bound runtime bundles. Opt-in serializers; never unpickle tool data."""
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from .model import canonical, digest, require
from .store import Store


def layout(cls):
    return {'name':cls.__name__,'size':ctypes.sizeof(cls),
        'fields':[[name,getattr(cls,name).offset,ctypes.sizeof(kind)] for name,kind,*_ in cls._fields_]}


def encode(value, arrays):
    import numpy as np
    if isinstance(value,np.ndarray):
        require(not value.dtype.hasobject,'checkpoint_unsupported','Object arrays cannot be checkpointed')
        name='array-'+str(len(arrays))+'.npy'; arrays[name]=value
        return {'$array':name}
    if isinstance(value,np.generic): return encode(value.item(),arrays)
    if isinstance(value,ctypes.Structure):
        return {'$struct':layout(type(value)), 'bytes':base64.b64encode(bytes(value)).decode()}
    if isinstance(value,set): return {'$set':[encode(x,arrays) for x in sorted(value,key=repr)]}
    if isinstance(value,tuple): return {'$tuple':[encode(x,arrays) for x in value]}
    if isinstance(value,list): return [encode(x,arrays) for x in value]
    if isinstance(value,dict):
        require(all(isinstance(k,(str,int,bool,float,tuple)) for k in value),'checkpoint_unsupported','Unsupported mapping key')
        return {'$dict':[[encode(k,arrays),encode(v,arrays)] for k,v in value.items()]}
    require(value is None or isinstance(value,(str,int,float,bool)), 'checkpoint_unsupported','Explicit serializer required for '+type(value).__name__)
    # Infinity is sometimes a not-yet-measured evaluator sentinel; encode explicitly.
    if isinstance(value,float) and not __import__('math').isfinite(value): return {'$float':repr(value)}
    return value


def decode(value,root,structs):
    import numpy as np
    if isinstance(value,list): return [decode(x,root,structs) for x in value]
    if not isinstance(value,dict): return value
    if '$array' in value:
        Store.safe_name(value['$array']);return np.load(root/value['$array'],allow_pickle=False)
    if '$set' in value: return {decode(x,root,structs) for x in value['$set']}
    if '$dict' in value: return {decode(k,root,structs):decode(v,root,structs) for k,v in value['$dict']}
    if '$tuple' in value: return tuple(decode(x,root,structs) for x in value['$tuple'])
    if '$float' in value:
        require(value['$float'] in {'inf','-inf','nan'},'integrity_error','Invalid float tag');return float(value['$float'])
    if '$struct' in value:
        cls=structs.get(value['$struct']['name'])
        require(cls is not None and layout(cls)==value['$struct'],'checkpoint_incompatible','C struct layout differs')
        raw=base64.b64decode(value['bytes'],validate=True)
        require(len(raw)==ctypes.sizeof(cls),'integrity_error','C state size differs')
        return cls.from_buffer_copy(raw)
    return {k:decode(v,root,structs) for k,v in value.items()}


def save_bundle(destination,binding,state,required):
    """Caller must pause at a coherent step boundary, then submit this saved bundle."""
    import numpy as np
    destination=Path(destination).absolute()
    require(not destination.exists(),'conflict','Checkpoint is immutable; choose a new path')
    require(set(required)<=set(state),'checkpoint_incomplete','Required subsystem state missing')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.checkpoint-',dir=destination.parent))
    try:
        arrays={};tree=encode(state,arrays)
        (temp/'state.json').write_text(canonical(tree))
        for name,array in arrays.items(): np.save(temp/name,array,allow_pickle=False)
        files={}
        for p in temp.iterdir():
            with open(p,'rb') as f: os.fsync(f.fileno())
            raw=p.read_bytes(); files[p.name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
        manifest={'schema_version':1,'binding':binding,'required':sorted(required),'files':files,
            'boundary':'after_complete_step','scope':'declared subsystem serializers; not arbitrary tool process memory'}
        (temp/'manifest.json').write_text(canonical(manifest))
        with open(temp/'manifest.json','rb') as f: os.fsync(f.fileno())
        temp.rename(destination)
        fd=os.open(str(destination.parent),os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return {'path':str(destination),'manifest_sha256':digest(manifest),'binding':binding}
    finally:
        if temp.exists(): shutil.rmtree(temp)


def load_bundle(path,expected_binding,manifest_sha256,structs=None):
    root=Path(path);manifest=json.loads((root/'manifest.json').read_text())
    require(digest(manifest)==manifest_sha256,'integrity_error','Checkpoint manifest differs')
    require(manifest['schema_version']==1,'checkpoint_incompatible','Unsupported checkpoint schema')
    require(manifest['binding']==expected_binding,'checkpoint_incompatible','Input/model/evaluator/environment differs')
    for name,info in manifest['files'].items():
        Store.safe_name(name);p=root/name
        require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'integrity_error','Checkpoint file missing or redirected')
        raw=p.read_bytes()
        require(len(raw)==info['size'] and hashlib.sha256(raw).hexdigest()==info['sha256'],'integrity_error','Checkpoint file corrupt')
    tree=json.loads((root/'state.json').read_text())
    def check_arrays(x):
        if isinstance(x,dict):
            if '$array' in x: require(x['$array'] in manifest['files'],'integrity_error','Unlisted array reference')
            for v in x.values(): check_arrays(v)
        elif isinstance(x,list):
            for v in x: check_arrays(v)
    check_arrays(tree)
    state=decode(tree,root,structs or {})
    require(set(manifest['required'])<=set(state),'checkpoint_incomplete','Required state missing')
    return state


def capture_coupled(model,data,drive,evaluator):
    import mujoco
    import numpy as np
    import random
    spec=int(mujoco.mjtState.mjSTATE_INTEGRATION)
    values=np.empty(mujoco.mj_stateSize(model,spec));mujoco.mj_getState(model,data,values,spec)
    # Every CDrive attribute except its dynamic library handle is serialized. New
    # unsupported types fail closed, instead of silently dropping internal state.
    driver={k:v for k,v in vars(drive).items() if k!='lib'}
    return {'mujoco':{'spec':spec,'values':values,'warning_number':data.warning.number.copy(),
            'warning_lastinfo':data.warning.lastinfo.copy()},
        'model_mutable':{'actuator_biasprm':model.actuator_biasprm.copy()},
        'driver':driver,'evaluator':evaluator,'random':random.getstate(),'numpy_random':np.random.get_state()}


def restore_coupled(state,model,data,drive):
    import mujoco
    import numpy as np
    import random
    require(set(state['driver'])==set(vars(drive))-{'lib'},'checkpoint_incompatible','Driver state schema changed')
    require(state['mujoco']['spec']==int(mujoco.mjtState.mjSTATE_INTEGRATION),'checkpoint_incompatible','MuJoCo state mask changed')
    require(state['mujoco']['values'].shape==(mujoco.mj_stateSize(model,state['mujoco']['spec']),),'checkpoint_incompatible','MuJoCo dimensions changed')
    model.actuator_biasprm[:]=state['model_mutable']['actuator_biasprm']
    for k,v in state['driver'].items(): setattr(drive,k,v)
    mujoco.mj_setState(model,data,state['mujoco']['values'],state['mujoco']['spec'])
    # Derived geometry is rebuilt. Reinstate integration/warmstart after forward.
    mujoco.mj_forward(model,data)
    mujoco.mj_setState(model,data,state['mujoco']['values'],state['mujoco']['spec'])
    data.warning.number[:]=state['mujoco']['warning_number'];data.warning.lastinfo[:]=state['mujoco']['warning_lastinfo']
    random.setstate(state['random']);np.random.set_state(state['numpy_random'])
    return state['evaluator']


def runtime_environment():
    """Adapter compatibility fingerprint; no credentials or general environment dump."""
    import importlib.metadata
    import platform
    import subprocess
    packages={}
    for name in ('mujoco','numpy','numba','llvmlite'):
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]='not_installed'
    compiler=subprocess.run(['clang','--version'],capture_output=True,text=True,check=True,timeout=10)
    return {'packages':packages,'python':platform.python_version(),'python_compiler':platform.python_compiler(),
        'machine':platform.machine(),'os':platform.system(),'os_release':platform.release(),
        'c_compiler':compiler.stdout.splitlines()[0]}
