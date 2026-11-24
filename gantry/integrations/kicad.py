"""Operator-local rule checks on a staged copy of a trusted KiCad design."""
import os
from pathlib import Path
import subprocess
import tempfile

from ..model import digest, require, Fault
from .bundle import MAX_TOTAL, make_bundle, read_file
from .transport import parse_json

CHECKS = {'.kicad_pcb': ('pcb', 'drc'), '.kicad_sch': ('sch', 'erc')}
SUPPORT = {'.kicad_pro', '.kicad_dru', '.kicad_sym', '.kicad_mod', *CHECKS}


def _run_check(binary, argv, scratch):
    home = scratch / 'home'
    home.mkdir()
    temp = scratch / 'temp'
    temp.mkdir()
    env = {'PATH': os.defpath, 'HOME': str(home), 'USERPROFILE': str(home),
           'KICAD_CONFIG_HOME': str(home/'config'), 'XDG_CACHE_HOME': str(home/'cache'),
           'TMPDIR': str(temp), 'TEMP': str(temp), 'TMP': str(temp)}
    if os.name == 'nt':
        env['SystemRoot'] = os.environ['SystemRoot']
        env['PATH'] = str(Path(env['SystemRoot'])/'System32')
        env['APPDATA'] = env['LOCALAPPDATA'] = str(home)
    try:
        return subprocess.run([str(binary), *argv], cwd=scratch/'design', env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=120, check=False).returncode
    except subprocess.TimeoutExpired:
        raise Fault('tool_timeout', 'KiCad rule check exceeded 120 seconds') from None


def _counts(report, check):
    def count(items):
        require(isinstance(items, list), 'capture_incomplete', 'Invalid KiCad report entries')
        return len(items)

    if check == 'drc':
        return {name: count(report.get(name)) for name in ('violations', 'unconnected_items', 'schematic_parity')}
    sheets = report.get('sheets')
    require(isinstance(sheets, list) and all(isinstance(sheet, dict) for sheet in sheets),
            'capture_incomplete', 'Invalid KiCad ERC sheets')
    return {'violations': sum(count(sheet.get('violations')) for sheet in sheets), 'sheets': len(sheets)}


def check_kicad(root, document, dependencies, executable, source_id, refs):
    root = Path(root).resolve()
    executable = Path(executable)
    require(executable.is_absolute(), 'invalid_input', 'Select an installed kicad-cli by absolute path')
    binary = executable.resolve()
    require(binary.is_file() and binary.name.lower() in {'kicad-cli', 'kicad-cli.exe'}
            and os.access(binary, os.X_OK) and not binary.is_relative_to(root),
            'scope_denied', 'KiCad CLI must be installed outside the design directory')
    part = Path(document)
    require(part.suffix in CHECKS, 'unsupported', 'Select a KiCad board or schematic')
    names = [document, *dependencies]
    for ext in ('.kicad_pro', '.kicad_dru'):
        name = part.with_suffix(ext).as_posix()
        if name not in names and (root/name).exists():
            names.append(name)
    require(len(names) <= 99 and len(set(n.casefold() for n in names)) == len(names),
            'invalid_input', 'Select distinct KiCad input paths')
    files = {}
    size = 0
    for name in names:
        require(Path(name).suffix in SUPPORT, 'unsupported', 'Unsupported KiCad dependency')
        raw = read_file(root, name)
        size += len(raw)
        require(size <= MAX_TOTAL, 'acquisition_limit', 'KiCad inputs exceed capture limit')
        files['design/'+name] = raw

    # Apply the regular scope, secret and requirement checks before sending inputs to KiCad.
    basis = make_bundle('kicad', source_id, files, refs)
    domain, check = CHECKS[part.suffix]
    with tempfile.TemporaryDirectory(prefix='gantry-kicad-') as directory:
        scratch = Path(directory)
        for name, raw in files.items():
            target = scratch/name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
        argv = [domain, check, '--format', 'json', '--exit-code-violations', '--output',
                str(scratch/'report.json'), str(scratch/'design'/document)]
        code = _run_check(binary, argv, scratch)
        require(code in (0, 5), 'tool_failed', f'KiCad {check.upper()} exited with code {code}')
        raw_report = read_file(scratch, 'report.json')
    report = parse_json(raw_report)
    require(isinstance(report, dict) and report.get('$schema') == f'https://schemas.kicad.org/{check}.v1.json'
            and report.get('source') == part.name and isinstance(report.get('kicad_version'), str)
            and report['kicad_version'], 'capture_incomplete', 'Unexpected KiCad report source, version or schema')
    files['checks/'+check+'.json'] = raw_report
    source = {'kind': 'kicad_cli_check', 'check': check, 'document': document,
              'kicad_version': report['kicad_version'], 'exit_code': code,
              'outcome': 'findings' if code == 5 else 'no_reported_violations',
              'counts': _counts(report, check)}
    return make_bundle('kicad', source_id, files, refs, source=source,
                       source_revision=digest(basis['manifest']['files']),
                       missing=['unstaged libraries or design dependencies', 'unsaved edits', 'physical validation'])
