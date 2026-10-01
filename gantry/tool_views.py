"""Explicit output profiles over saved evidence; never rewrite native artifacts."""
import copy
import math

from .model import canonical, digest, require

UNITS = {'m': ('length', 1), 'mm': ('length', .001), 'cm': ('length', .01),
         's': ('time', 1), 'ms': ('time', .001), 'rad': ('angle', 1),
         'deg': ('angle', math.pi / 180), 'kg': ('mass', 1), 'g': ('mass', .001)}


def _scale(value, factor):
    if isinstance(value, list):
        return [_scale(v, factor) for v in value]
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
            'invalid_input', 'Unit conversion needs finite numeric values')
    result = value * factor
    require(math.isfinite(result), 'invalid_input', 'Unit conversion overflow')
    return result


def render(view, profile):
    fields = {f['name']: f for f in view['fields']}
    output, provenance, missing, selected, written = {}, [], [], set(), []
    for item in profile['fields']:
        require(item['source'] in fields, 'not_found', 'Requested source field is not captured')
        field = fields[item['source']]; value = copy.deepcopy(field['value']); factor = 1
        selected.add(item['source'])
        if field['classification'] != 'unknown':
            for dimension in ('frame', 'time_basis'):
                if dimension in item:
                    require(item[dimension] == field.get(dimension), 'mapping_required',
                            'An explicit coordinate/time transform is required', field=item['source'])
            if 'unit' in item and item['unit'] != field.get('unit'):
                before, after = UNITS.get(field.get('unit')), UNITS.get(item['unit'])
                require(before and after and before[0] == after[0], 'mapping_required', 'Unsupported or unspecified unit conversion')
                factor = before[1] / after[1]; value = _scale(value, factor)
        else:
            value = None; missing.append(item['target'])
        pointer = item['target']
        require(pointer.startswith('/') and pointer != '/', 'invalid_input', 'Nonempty output JSON Pointer required')
        keys = [part.replace('~1', '/').replace('~0', '~') for part in pointer[1:].split('/')]
        require(not any(keys[:len(old)] == old or old[:len(keys)] == keys for old in written),
                'invalid_input', 'Overlapping output paths')
        written.append(keys)
        node = output
        for key in keys[:-1]:
            if key not in node: node[key] = {}
            require(isinstance(node[key], dict), 'invalid_input', 'Overlapping output paths')
            node = node[key]
        require(keys[-1] not in node, 'invalid_input', 'Duplicate/overlapping output paths')
        node[keys[-1]] = value
        require(len(canonical(output).encode()) <= 1048576, 'invalid_input', 'Rendered data exceeds 1 MiB')
        provenance.append({'source_field': field['name'], 'target': pointer,
            'classification': field['classification'], 'source': view['sources'][field['source_index']],
            'method': field['method'], 'source_unit': field.get('unit'), 'output_unit': item.get('unit', field.get('unit')),
            'scale': factor, 'frame': field.get('frame'), 'time_basis': field.get('time_basis')})
    return {'data': output, 'view_id': view['id'], 'state_id': view['state_id'],
        'profile': copy.deepcopy(profile), 'profile_hash': digest(profile), 'provenance': provenance,
        'missing': missing, 'omitted_fields': sorted(set(fields) - selected),
        'limitations': ['Declared mapping, not inferred tool compatibility',
            'No coordinate/time transforms or CAD topology conversion', 'No validation or adoption implied']}
