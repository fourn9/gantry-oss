"""Run in the installed FreeCAD Python ABI as an isolated child, in a scratch folder."""
import json
import math
from pathlib import Path
import sys


def main():
    sys.path.insert(0, sys.argv[1])
    import FreeCAD as app
    import Part

    root = Path.cwd()
    shape = Part.read(str(root/'input.step'))
    if shape.isNull():
        raise ValueError('Empty STEP')
    doc = app.newDocument('StepImport')
    feature = doc.addObject('Part::Feature', 'Imported')
    feature.Shape = shape
    doc.recompute()
    path = str(root/'import.FCStd')
    doc.saveAs(path)
    app.closeDocument(doc.Name)
    reopened = app.openDocument(path)
    saved = reopened.getObject('Imported').Shape
    if (saved.isNull() or len(saved.Solids) != len(shape.Solids) or len(saved.Faces) != len(shape.Faces)
            or not math.isclose(shape.Volume, saved.Volume, abs_tol=1e-7, rel_tol=1e-8)):
        raise ValueError('STEP import changed on reopen')
    report = {'freecad_version': '.'.join(app.Version()[:3]), 'solids': len(saved.Solids),
              'faces': len(saved.Faces), 'volume_mm3': saved.Volume, 'kernel_valid': saved.isValid(),
              'reopened': True}
    (root/'inspection.json').write_text(json.dumps(report, allow_nan=False))
    app.closeDocument(reopened.Name)


if __name__ == '__main__':
    main()
