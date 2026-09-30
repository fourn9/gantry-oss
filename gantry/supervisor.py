"""Credential-free local process supervisor. Its receipt is durable, never a PID guess.

Launch intent without a receipt is deliberately ambiguous: automatic relaunch is
forbidden. A wall-clock deadline plus a monotonic upper bound limit offline work.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def write(path, value):
    path = Path(path); tmp = path.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        os.chmod(tmp, 0o600); json.dump(value, f, sort_keys=True); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(str(path.parent), os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def main(root):
    root = Path(root); spec = json.loads((root/'job.json').read_text())
    # Exclusive job identity prevents a second supervisor from starting this job.
    import fcntl
    with open(root/'job.lock', 'a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return
        if (root/'receipt.json').exists(): return
        started = time.time(); bound = time.monotonic() + max(0, spec['deadline']-started)
        receipt = {'job_id': spec['job_id'], 'phase':'starting', 'started_at':started}
        write(root/'receipt.json', receipt)
        code = -1; reason = 'launch_failed'
        with open(root/'stdout.log','ab') as out, open(root/'stderr.log','ab') as err:
            proc = None
            try:
                if started >= spec['deadline']: reason = 'deadline'
                else:
                    proc = subprocess.Popen(spec['argv'], cwd=root/'workspace', env=spec['env'],
                        stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
                    receipt.update(phase='running', pid=proc.pid); write(root/'receipt.json', receipt)
                    reason = 'completed'
                    while proc.poll() is None:
                        lease = json.loads((root/'lease.json').read_text())
                        if lease['job_id'] != spec['job_id'] or lease.get('cancel'): reason = 'cancelled'; break
                        if time.time() >= spec['deadline'] or time.monotonic() >= bound: reason = 'deadline'; break
                        if time.time() >= lease['expires_at']: reason = 'connection_lease_expired'; break
                        time.sleep(0.05)
            except Exception as exc:
                reason = 'supervisor_error'; err.write(str(exc).encode())
            finally:
                if proc:
                    if proc.poll() is None:
                        try: os.killpg(proc.pid, signal.SIGTERM)
                        except ProcessLookupError: pass
                        try: proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL); proc.wait()
                    code = proc.returncode
                receipt.update(phase='finished', exit_code=code, reason=reason, finished_at=time.time())
                write(root/'receipt.json',receipt)

if __name__ == '__main__': main(sys.argv[1])
