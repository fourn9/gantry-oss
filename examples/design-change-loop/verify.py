"""Native B-rep screening of an anonymous carrier; not strength/dynamic validation."""
import hashlib
import json
from pathlib import Path
from gantry import cad_kernel as cq

root = Path('.')
read = lambda p: json.loads((root/p).read_text())
design, control, calibration = [read(p) for p in ('design.json','control.json','calibration.json')]
fixed = cq.box(10,10,10)
carrier = cq.box(10,10,10).translate((design['carrier_x_mm'],0,0))
for name, shape in [('fixed.step',fixed),('carrier.step',carrier)]:
    cq.export_step(shape,str(root/name))
intersection = fixed.intersect(carrier).Volume()
clearance = fixed.distance(carrier)
measurements = {
    'overlap': {'value':intersection,'unit':'mm3'},
    'clearance': {'value':clearance,'unit':'mm'},
    'carrier_x': {'value':design['carrier_x_mm'],'unit':'mm'},
    'control_error': {'value':abs(control['target_mm']+calibration['offset_mm']-design['carrier_x_mm']),'unit':'mm'}}
plan = read('physical-plan.json')
for check in plan['checks']:
    report = {'status':'completed', 'inputs':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in check['inputs']},
        'requirement_refs':check['requirement_refs'], 'conditions':check['conditions'], 'evaluator':check['evaluator'],
        'environment':{'cad_backend':cq.BACKEND}, 'measurements':measurements,
        'limitations':['Static nominal solids only; no load, motion, tolerance or physical validation']}
    (root/check['report']).write_text(json.dumps(report,sort_keys=True))
print(json.dumps(measurements,sort_keys=True))
