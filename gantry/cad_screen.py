"""Bounded, snapshot-local CAD screening; optional CadQuery adapter.

No global monkey patch or persistent cache of mutable shapes. Build fresh bounds
after every geometry/pose change. Native files and exact narrow-phase checks stay
authoritative; this is not continuous-motion or physical certification.
"""
import hashlib
import json
import math
from pathlib import Path
import time
from types import MappingProxyType

from .model import digest, require


def capture_bounds(shapes):
    """Capture immutable numeric bounds once per named shape in one fixed pose."""
    started = time.perf_counter(); result = {}
    for name, shape in shapes.items():
        box = shape.BoundingBox()
        result[name] = ((box.xmin, box.ymin, box.zmin), (box.xmax, box.ymax, box.zmax))
        require(all(math.isfinite(v) for row in result[name] for v in row)
                and all(lo <= hi for lo, hi in zip(*result[name])),
                'invalid_geometry', 'Invalid bounding box')
    return MappingProxyType(result), {'bounds_computations': len(result),
                                    'bounds_seconds': time.perf_counter() - started}


def lower_bound(a, b):
    return math.sqrt(sum(max(0, b[0][i] - a[1][i], a[0][i] - b[1][i]) ** 2 for i in range(3)))


def screen(root, request):
    """Screen explicit pairs of hash-pinned STEP files in a declared common frame.

    Supported input: parts [{id,path,sha256}], pairs [[id,id]], clearance,
    overlap_tolerance, unit, frame. Unknown transforms must be resolved upstream.
    """
    started = time.perf_counter(); root = Path(root).resolve()
    require(isinstance(request, dict), 'invalid_input', 'CAD request must be an object')
    parts, pairs = request.get('parts'), request.get('pairs')
    require(isinstance(parts, list) and 1 <= len(parts) <= 1000, 'invalid_input', 'Provide 1–1000 parts')
    require(isinstance(pairs, list) and 1 <= len(pairs) <= 20000, 'invalid_input', 'Provide 1–20000 explicit pairs')
    require(request.get('unit') in {'mm', 'm'} and isinstance(request.get('frame'), str) and request['frame'],
            'invalid_input', 'Explicit common frame and native length unit required')
    clearance, volume_tolerance = request.get('clearance'), request.get('overlap_tolerance')
    require(all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
                for v in (clearance, volume_tolerance)), 'invalid_input', 'Finite nonnegative thresholds required')
    paths, sources = {}, []
    for part in parts:
        require(isinstance(part, dict) and isinstance(part.get('id'), str) and part['id'] and part['id'] not in paths,
                'invalid_input', 'Unique part ID required')
        name = Path(part.get('path', ''))
        require(not name.is_absolute() and '..' not in name.parts, 'scope_denied', 'Relative CAD path required')
        path = root / name
        require(not any(p.is_symlink() for p in (path, *path.parents) if p != root.parent)
                and path.resolve().is_relative_to(root) and path.is_file(), 'scope_denied', 'Regular CAD file inside root required')
        require(path.suffix.lower() in {'.step', '.stp'} and path.stat().st_size <= 100 * 1024 * 1024,
                'invalid_input', 'Only bounded STEP inputs supported')
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        require(fingerprint == part.get('sha256'), 'stale_basis', 'CAD source hash changed', part=part['id'])
        paths[part['id']] = path
        sources.append({'id': part['id'], 'path': name.as_posix(), 'sha256': fingerprint})
    require(all(isinstance(pair, list) and len(pair) == 2 and all(isinstance(n, str) and n in paths for n in pair)
                and pair[0] != pair[1] for pair in pairs), 'invalid_input', 'Pairs must reference two captured parts')
    import cadquery as cq
    import_started = time.perf_counter()
    shapes = {name: cq.importers.importStep(str(path)).val() for name, path in paths.items()}
    require(all(shape.isValid() and shape.Solids() for shape in shapes.values()),
            'invalid_geometry', 'Screening requires valid solid geometry')
    for source in sources:
        require(hashlib.sha256(paths[source['id']].read_bytes()).hexdigest() == source['sha256'],
                'stale_basis', 'Source changed during CAD import')
    imported = time.perf_counter() - import_started
    bounds, metrics = capture_bounds(shapes)
    rows, exact, rejected = [], 0, 0
    check_started = time.perf_counter()
    for first, second in pairs:
        distance_bound = lower_bound(bounds[first], bounds[second])
        row = {'parts': [first, second], 'bounds_distance': distance_bound}
        if distance_bound > clearance + 1e-9:
            rejected += 1
            row.update(method='bounds_separated', clearance_satisfied=True, exact_distance=None, overlap_volume=None)
        else:
            exact += 1
            gap = shapes[first].distance(shapes[second])
            volume = max(0, shapes[first].intersect(shapes[second]).Volume())
            require(math.isfinite(gap) and math.isfinite(volume), 'invalid_geometry', 'Nonfinite geometry result')
            row.update(method='exact', exact_distance=gap, overlap_volume=volume,
                       clearance_satisfied=gap >= clearance and volume <= volume_tolerance)
        rows.append(row)
    metrics.update(import_seconds=imported, check_seconds=time.perf_counter() - check_started,
                   total_seconds=time.perf_counter() - started, pairs=len(pairs), bounds_separated=rejected,
                   exact_pairs=exact)
    return {'adapter': 'gantry.cad-screen.v1', 'backend': 'CadQuery ' + cq.__version__,
        'request_hash': digest(request), 'sources': sources, 'unit': request['unit'], 'frame': request['frame'],
        'pairs': rows, 'passed_requested_pairs': all(r['clearance_satisfied'] for r in rows), 'metrics': metrics,
        'limitations': ['One declared pose and explicit pairs only', 'Units/frame are submitted declarations',
                       'No continuous sweep, flexible bodies, loads, or formal adoption'],
        'unrequested_pair_count': len(parts) * (len(parts) - 1) // 2 - len({tuple(sorted(p)) for p in pairs})}


def main():
    import argparse
    from .runner import persist
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True); parser.add_argument('--request', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    require(not output.exists() and not output.is_symlink(), 'conflict', 'Use a new result path')
    result = screen(args.root, json.loads(Path(args.request).read_text()))
    persist(output, result)
    print(json.dumps({'passed_requested_pairs': result['passed_requested_pairs'], 'metrics': result['metrics']}))


if __name__ == '__main__':
    main()
