"""Synthetic configuration check only. This is not a physical simulation."""
import json
from pathlib import Path

mechanical = json.loads(Path('mechanical.json').read_text())
control = json.loads(Path('control.json').read_text())
assert mechanical['joint_id'] == control['joint_id'] == 'joint-1'
assert mechanical['travel_deg'] == control['travel_deg'] == 60
print('Configuration agreement: pass. Geometry, loads and physical safety: unverified.')
