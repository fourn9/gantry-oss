"""Read-only native geometry + executable command filter; fixed acceptance."""
import hashlib,json
from pathlib import Path
from gantry import cad_kernel as cad
from controller import simulate
read=lambda p:json.loads(Path(p).read_text())
design,control,calibration=[read(p) for p in ('design.json','control.json','calibration.json')]
fixed,carrier=[cad.import_step(p) for p in ('fixed.step','carrier.step')]
trace=simulate(control['target_mm'],calibration['offset_mm'])
box=carrier.BoundingBox(); x=(box.xmin+box.xmax)/2
measurements={
 'overlap':{'value':fixed.intersect(carrier).Volume(),'unit':'mm3'},
 'clearance':{'value':fixed.distance(carrier),'unit':'mm'},
 'carrier_x':{'value':x,'unit':'mm'},
 'cad_source_error':{'value':abs(x-design['carrier_x_mm']),'unit':'mm'},
 'control_error':{'value':abs(trace[-1]['position_mm']-x),'unit':'mm'}}
Path('trace.json').write_text(json.dumps(trace))
for check in read('physical-plan.json')['checks']:
    report={'status':'completed','inputs':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in check['inputs']},
      'requirement_refs':check['requirement_refs'],'conditions':check['conditions'],'evaluator':check['evaluator'],
      'environment':{'cad_backend':cad.BACKEND},'measurements':measurements,
      'limitations':['Nominal static CAD and software filter only; no dynamics, load, electrical, tolerance or hardware test']}
    Path(check['report']).write_text(json.dumps(report,sort_keys=True))
print(json.dumps(measurements))
