"""Local payload-free phase intervals. Elapsed time is not CPU or model thinking time."""
from contextlib import contextmanager
import json
from pathlib import Path
import time
import uuid

from .runner import persist

PHASES={'context','model','action','record','checkpoint','recovery'}


@contextmanager
def span(root, phase):
    if phase not in PHASES: raise ValueError('Unknown timing phase')
    directory=Path(root)/'timing'; directory.mkdir(mode=0o700,exist_ok=True)
    if directory.is_symlink(): raise ValueError('Timing directory cannot be a symlink')
    path=directory/(uuid.uuid4().hex+'.json')
    record={'schema':1,'phase':phase,'status':'started','started_at_ns':time.time_ns(),
        'finished_at_ns':None,'monotonic_seconds':None}
    start=time.monotonic_ns(); persist(path,record)
    try:
        yield
    except BaseException:
        record['status']='failed'
        raise
    else: record['status']='completed'
    finally:
        record.update(finished_at_ns=time.time_ns(),monotonic_seconds=(time.monotonic_ns()-start)/1e9)
        persist(path,record)


def summarize(root):
    phases={}; intervals=[]; incomplete=0; invalid=0
    for path in Path(root).rglob('timing/*.json'):
        if path.is_symlink(): invalid+=1; continue
        try:
            row=json.loads(path.read_text()); phase=row['phase']
            if row.get('schema')!=1 or phase not in PHASES: raise ValueError()
            start=row['started_at_ns']; end=row.get('finished_at_ns')
            if end is None: incomplete+=1; continue
            duration=row['monotonic_seconds']
            if type(start)!=int or type(end)!=int or end<start or not isinstance(duration,(int,float)) or duration<0:
                raise ValueError()
            item=phases.setdefault(phase,{'count':0,'failed':0,'wall_seconds':0,'monotonic_seconds':0})
            item['count']+=1; item['failed']+=row.get('status')=='failed'
            item['wall_seconds']+=(end-start)/1e9; item['monotonic_seconds']+=duration
            intervals.append((start,end))
        except (OSError, ValueError, KeyError, TypeError): invalid+=1
    covered=0; last=None
    for start,end in sorted(intervals):
        if last is None or start>last:
            covered+=end-start; last=end
        elif end>last: covered+=end-last; last=end
    return {'schema':1,'phases':phases,'covered_wall_seconds':covered/1e9,
        'incomplete':incomplete,'invalid':invalid,
        'meaning':'Phase sums may overlap across workers. Covered wall time is their union. '
                  'Model spans include CLI/provider/network waiting. Clock differences do not prove sleep. '
                  'Host suspension needs separate OS evidence; operator labor and uncovered waits are not measured.'}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal',type=Path)
    print(json.dumps(summarize(parser.parse_args().journal),indent=2))
