"""Generate anonymous nominal CAD from design parameters; no solver claims."""
import json
from pathlib import Path
from gantry import cad_kernel as cad
p=json.loads(Path('design.json').read_text())
cad.export_step(cad.box(10,10,10),'fixed.step')
cad.export_step(cad.box(10,10,10).translate((p['carrier_x_mm'],0,0)),'carrier.step')
print(json.dumps({'built':['fixed.step','carrier.step'],'backend':cad.BACKEND}))
