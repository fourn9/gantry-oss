"""Offline maintenance baseline check, not a vulnerability scanner or attestation."""
import importlib.metadata
import json
import platform
import re
import sys

REVIEWED_AT = '2026-10-24'
PYTHON_FLOORS = {(3, 11): 17, (3, 12): 15, (3, 13): 17, (3, 14): 9, (3, 15): 1}
PACKAGE_FLOORS = {'pip': '26.2.2', 'certifi': '2026.10.19', 'uv': '0.13.4',
                  'PyNaCl': '1.6.2', 'setuptools': '78.1.1'}


def release(value):
    # Unknown/vendor/prerelease versions require operator review, not a green check.
    if not re.fullmatch(r'\d+\.\d+\.\d+', value):
        return None
    return tuple(map(int, value.split('.')))


def assess(python_version, packages, implementation='CPython'):
    findings = []
    version = release(python_version)
    minimum = PYTHON_FLOORS.get(version[:2]) if version else None
    if implementation != 'CPython' or minimum is None:
        findings.append({'component': 'Python', 'installed': python_version,
                         'action': 'Unreviewed runtime; verify vendor security support and backports'})
    elif version[2] < minimum:
        findings.append({'component': 'Python', 'installed': python_version,
                         'minimum': '.'.join(map(str, (*version[:2], minimum))),
                         'action': 'Update interpreter or independently verify vendor backports'})
    for name, floor in PACKAGE_FLOORS.items():
        if name not in packages:
            continue
        installed = release(packages[name])
        if installed is None or installed < release(floor):
            findings.append({'component': name, 'installed': packages[name], 'minimum': floor,
                             'action': 'Update in this environment; see SECURITY-UPDATES.md'})
    return {'reviewed_at': REVIEWED_AT, 'python': python_version,
            'implementation': implementation,
            'packages': {key: packages[key] for key in PACKAGE_FLOORS if key in packages},
            'findings': findings,
            'limitations': ['This is a dated baseline, not an all-CVE scan or safety guarantee.',
                'OS trust store, OpenSSL, proxies, native libraries and external tools need separate review.',
                'Only package metadata in this interpreter is checked; other environments and standalone uv are not.',
                'Run pip-audit for current package advisories. No data is sent by this command.']}


def main():
    packages = {}
    for name in PACKAGE_FLOORS:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    result = assess(platform.python_version(), packages, platform.python_implementation())
    print(json.dumps(result, indent=2))
    return 1 if result['findings'] else 0


if __name__ == '__main__':
    sys.exit(main())
