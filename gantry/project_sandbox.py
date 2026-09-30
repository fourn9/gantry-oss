"""Opt-in test execution in a scratch copy. Never fall back to host execution."""
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import sysconfig
import time

from .model import Fault, require


def backend():
    if platform.system() == 'Darwin' and Path('/usr/bin/sandbox-exec').is_file(): return 'macos-seatbelt'
    if platform.system() == 'Linux' and shutil.which('bwrap'): return 'linux-bubblewrap'
    return 'unavailable'


def runtime_roots():
    # Runtime dependencies are trusted read-only inputs, explicitly listed in approval.
    roots = {str(Path(sys.base_prefix).resolve()), str(Path(sysconfig.get_path('stdlib')).resolve())}
    return sorted(p for p in roots if p not in {'/', str(Path.home()), '/Users', '/home', '/usr', '/usr/local'})


def invocation(command, scratch, runtime, selected_backend):
    scratch = str(Path(scratch).resolve())
    require(selected_backend == backend() and selected_backend != 'unavailable',
            'sandbox_unavailable', 'No supported sandbox; execution refused')
    executable = Path(command['argv'][0])
    require(executable.is_absolute() and executable.is_file(), 'invalid_input', 'Approved absolute executable required')
    # Tool installations may be read, never the project, home or credentials.
    allowed_runtime = runtime_roots()
    require(runtime == allowed_runtime, 'reauthorization_required', 'Runtime installation changed')
    argv = list(command['argv'])
    if selected_backend == 'macos-seatbelt':
        reads = ['/System', '/usr/lib', '/usr/share', '/usr/bin', '/bin',
                 '/Library/Apple', '/Library/Developer/CommandLineTools', '/private/etc/localtime',
                 '/dev/null', '/dev/random', '/dev/urandom', scratch, *runtime]
        require(any(executable.resolve().is_relative_to(Path(p)) for p in reads),
                'reauthorization_required', 'Executable outside approved runtime')
        rules = ['(version 1)', '(deny default)', '(allow process-exec process-fork)',
                 '(allow signal (target self))', '(allow sysctl-read)',
                 '(allow mach-lookup (global-name "com.apple.system.logger"))',
                 '(allow file-read-metadata)', '(allow file-read-data (literal "/"))',
                 '(allow file-write* (literal "/dev/null"))']
        rules += ['(allow file-read* (subpath ' + json.dumps(p) + '))' for p in reads]
        rules += ['(allow file-write* (subpath ' + json.dumps(scratch) + '))']
        # Explicit exclusions override broad runtime read rules.
        rules += ['(deny file-read-data (regex #"(^|/)(\\.env[^/]*|[^/]*\\.(token|pem|key)|auth\\.json|credentials[^/]*|\\.netrc)$"))']
        return ['/usr/bin/sandbox-exec', '-p', '\n'.join(rules), *argv]
    mounts = [p for p in ['/usr', '/bin', '/lib', '/lib64', *runtime] if Path(p).exists()]
    require(any(executable.resolve().is_relative_to(Path(p).resolve()) for p in mounts),
            'reauthorization_required', 'Executable outside approved runtime')
    args = [shutil.which('bwrap'), '--die-with-parent', '--unshare-all', '--new-session',
            '--cap-drop', 'ALL', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    for path in mounts: args += ['--ro-bind', path, path]
    args += ['--bind', scratch, scratch, '--chdir', scratch, '--', *argv]
    return args


def execute(command, scratch, runtime, selected_backend, check_active):
    argv = invocation(command, scratch, runtime, selected_backend)
    scratch = Path(scratch); (scratch/'home').mkdir(); (scratch/'tmp').mkdir()
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(scratch/'home'), 'TMPDIR': str(scratch/'tmp'),
           'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}
    # Output file is opened by the bridge, never a credential-bearing pipe/environment.
    output = scratch/'.test-output'
    start = time.monotonic(); reason = None
    with output.open('w+b') as log:
        proc = subprocess.Popen(argv, cwd=scratch, env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        try:
            while proc.poll() is None:
                if time.monotonic() - start > command['timeout_seconds']: reason = 'timeout'
                elif output.stat().st_size > 1024*1024: reason = 'output_limit'
                else:
                    try: check_active()
                    except Fault: reason = 'connection_revoked_or_expired'
                if reason: break
                time.sleep(0.1)
        finally:
            # Kill the sandbox process group even when its direct child exited.
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait()
        log.seek(0); raw = log.read(1024*1024)
    check_active()
    return {'exit_code': proc.returncode, 'reason': reason, 'seconds': round(time.monotonic()-start, 3),
            'output': raw.decode('utf-8', errors='replace'), 'sandbox': selected_backend,
            'workspace_changes_applied': False}
