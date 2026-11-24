"""Import a selected neutral STEP in the installed Mac FreeCAD and reopen its FCStd."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from ..model import Fault, require
from .bundle import make_bundle, read_file
from .transport import parse_json


def capture_step(root, path, application, source_id, refs):
    require(Path(path).suffix.lower() in {'.step', '.stp'}, 'unsupported', 'Select a STEP file')
    raw = read_file(root, path)
    files = {'original/'+path: raw}
    make_bundle('freecad', source_id, files, refs)
    app = Path(application).resolve()
    resources = app/'Contents/Resources'
    python = resources/'bin/python'
    require(app.suffix == '.app' and python.is_file() and os.access(python, os.X_OK)
            and (resources/'lib/FreeCAD.so').is_file()
            and not app.is_relative_to(Path(root).resolve()), 'tool_unavailable',
            'Select an installed macOS FreeCAD application outside the design directory')
    script = Path(__file__).with_name('_freecad_import.py').resolve()
    with tempfile.TemporaryDirectory(prefix='gantry-freecad-') as directory:
        scratch = Path(directory)
        (scratch/'input.step').write_bytes(raw)
        home = scratch/'home'
        home.mkdir()
        env = {'HOME':str(home), 'TMPDIR':str(scratch), 'XDG_CONFIG_HOME':str(home),
               'XDG_CACHE_HOME':str(home), 'FREECAD_USER_HOME':str(home), 'PATH':os.defpath}
        try:
            result = subprocess.run([str(python), '-I', str(script), str(resources/'lib')],
                                    cwd=scratch, env=env, timeout=120, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise Fault('tool_timeout', 'FreeCAD STEP import exceeded 120 seconds') from None
        require(result.returncode == 0, 'tool_failed', 'FreeCAD could not import, save and reopen this STEP')
        files['geometry/import.FCStd'] = read_file(scratch, 'import.FCStd')
        files['geometry/inspection.json'] = read_file(scratch, 'inspection.json')
    view = parse_json(files['geometry/inspection.json'])
    return make_bundle('freecad', source_id, files, refs, {'geometry/inspection.json': ['/solids','/volume_mm3']},
                       source={'kind':'freecad_step_roundtrip', 'freecad_version':view['freecad_version'],
                               'input':path}, source_revision=hashlib.sha256(raw).hexdigest(),
                       missing=['source CAD feature tree and constraints', 'external references', 'physical validation'])
