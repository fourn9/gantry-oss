"""Freeze explicit, trusted experiment inputs. Never discover a whole workspace."""
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .connection_policy import safe_path, clean_bytes, MAX_FILE, MAX_FILES, MAX_TOTAL
from .model import require, digest, canonical
from . import project_sandbox


def environment():
    executable = Path(sys.executable).resolve()
    packages = sorted((d.metadata.get('Name', ''), d.version) for d in importlib.metadata.distributions())
    cli = shutil.which('codex')
    cli_version = subprocess.run([cli, '--version'], capture_output=True, text=True, timeout=10).stdout.strip() if cli else None
    return {'python': sys.version, 'executable': str(executable),
        'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
        'packages': packages, 'platform': platform.platform(), 'sandbox': project_sandbox.backend(),
        'runtime': project_sandbox.runtime_roots(), 'codex_cli': cli_version,
        'implementation_hash': digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob('*.py'))})}


def freeze_case(path):
    path = Path(path).resolve(); case = json.loads(path.read_text())
    require(isinstance(case, dict) and set(case) == {'name', 'project_root', 'files', 'write_scope',
        'goal', 'acceptance', 'verifier', 'experiences'}, 'invalid_input', 'Use the documented evaluation case fields')
    for key in ('name', 'goal', 'project_root'):
        require(isinstance(case[key], str) and case[key].strip(), 'invalid_input', 'Nonempty '+key+' required')
    require(isinstance(case['acceptance'], list) and case['acceptance'] and
        all(isinstance(x, str) and x for x in case['acceptance']), 'invalid_input', 'Explicit acceptance required')
    names, scope = case['files'], case['write_scope']
    require(isinstance(names, list) and 0 < len(names) <= MAX_FILES and all(isinstance(x, str) for x in names)
        and len(set(names)) == len(names), 'invalid_input', 'Select distinct files')
    require(isinstance(scope, list) and scope and all(isinstance(x, str) and x in names for x in scope),
        'invalid_input', 'Write scope must list selected files exactly')
    verifier = case['verifier']
    require(isinstance(verifier, dict) and set(verifier) == {'script', 'timeout_seconds'} and
        verifier['script'] in names and verifier['script'] not in scope and verifier['script'].endswith('.py') and
        type(verifier['timeout_seconds']) is int and 1 <= verifier['timeout_seconds'] <= 300,
        'invalid_input', 'Select a read-only Python verifier and a 1–300 second timeout')
    notes = case['experiences']
    require(isinstance(notes, list) and 0 < len(notes) <= 20, 'invalid_input', 'Select 1–20 prior experience notes')
    for note in notes:
        require(isinstance(note, dict) and set(note) == {'observation', 'applicability', 'source', 'limitations'} and
            all(isinstance(note[k], str) and 0 < len(note[k]) <= 4000 for k in ('observation','applicability','source')) and
            isinstance(note['limitations'], list) and note['limitations'] and
            all(isinstance(x, str) and x for x in note['limitations']), 'invalid_input', 'Experience needs source and limitations')
    clean_bytes(canonical(case).encode())
    source = path.parent / case['project_root']
    require(source.is_dir() and not any(p.is_symlink() for p in [source, *source.parents]),
        'scope_denied', 'Project root must not traverse symlinks')
    source = source.resolve(); files = {}; manifest = {}; total = 0
    for name in names:
        safe_path(name); selected = source/name
        require(selected.is_file() and not any(p.is_symlink() for p in [selected, *selected.parents]),
            'scope_denied', 'Selected files must be regular files without symlinks')
        with selected.open('rb') as stream: raw = clean_bytes(stream.read(MAX_FILE+1))
        total += len(raw)
        require(total <= MAX_TOTAL, 'capture_incomplete', 'Selected files exceed 32 MiB')
        files[name] = base64.b64encode(raw).decode(); manifest[name] = hashlib.sha256(raw).hexdigest()
    frozen = {k: v for k, v in case.items() if k not in {'project_root', 'files'}}
    frozen.update(files=files, manifest=manifest, environment=environment())
    frozen['case_hash'] = digest(frozen)
    return frozen
