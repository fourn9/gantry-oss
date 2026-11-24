"""Opt-in Fusion add-in for one named cloud DataFile on the Mac."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import adsk.core
import adsk.fusion
from .source_receipts import enqueue

_handler = None
_event = None


def run(context):
    global _event, _handler
    app = adsk.core.Application.get()
    config = json.loads(Path(__file__).with_name("enrollment.json").read_text())
    root = Path(config["workspace"]).resolve(strict=True)
    folder = root / config["exports"]
    if folder.resolve(strict=True) != folder or root not in folder.parents:
        raise ValueError("Use an existing export directory in the enrolled workspace")

    class Complete(adsk.core.DataEventHandler):
        def notify(self, args):
            try:
                version = args.file
                if version.id != config["data_file_id"]:
                    return
                doc = app.activeDocument
                if not doc or not doc.dataFile or doc.dataFile.versionId != version.versionId or doc.isModified:
                    app.log("Gantry held this save: reopen the exact saved version to export it.")
                    return
                design = adsk.fusion.Design.cast(app.activeProduct)
                if not design or doc.documentReferences.count:
                    app.log("Gantry held this save: use the Design workspace and a standalone design.")
                    return
                key = hashlib.sha256(version.versionId.encode()).hexdigest()
                target = folder / (key + ".f3d")
                # Export privately, then publish the completed filename once.
                with tempfile.TemporaryDirectory(dir=root / ".gantry") as scratch:
                    archive = Path(scratch) / "export.f3d"
                    mgr = design.exportManager
                    options = mgr.createFusionArchiveExportOptions(str(archive), design.rootComponent)
                    if not options or not mgr.execute(options) or doc.isModified or doc.dataFile.versionId != version.versionId:
                        raise ValueError("Cannot export the exact completed version")
                    try:
                        os.link(archive, target)
                    except FileExistsError:
                        # A duplicate callback must never relabel an unrelated existing export.
                        with archive.open("rb") as first, target.open("rb") as second:
                            while True:
                                chunk = first.read(1024**2)
                                if chunk != second.read(1024**2):
                                    raise ValueError("Existing export has different bytes")
                                if not chunk:
                                    break
                enqueue(root, "fusion-saved", target.relative_to(root), version.versionId)
                app.log("Gantry queued a completed design version.")
            except Exception as exc:
                app.log("Gantry save held: " + str(exc))

    _handler = Complete()
    _event = app.dataFileComplete
    _event.add(_handler)


def stop(context):
    global _handler, _event
    if _event and _handler:
        _event.remove(_handler)
    _handler = _event = None
