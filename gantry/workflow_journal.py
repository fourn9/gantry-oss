"""Private local request journal. Core remains the authoritative state store."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from .model import canonical, digest, require, uid


def connect(directory):
    root = Path(directory).absolute()
    require(not any(p.is_symlink() for p in [root, *root.parents]),
            'scope_denied', 'Journal must not traverse symlinks')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / 'workflow.sqlite3'
    require(not path.is_symlink(), 'scope_denied', 'Journal must not be a symlink')
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600); os.close(fd)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path, timeout=2)
    db.execute('CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, args TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS spans (id TEXT PRIMARY KEY, metadata TEXT NOT NULL, started REAL NOT NULL, ended REAL, seconds REAL, outcome TEXT)')
    return db


def freeze(directory, key, intent, prepare):
    """Serialize local preparation, then replay exact arguments through Core auth.

    Never cache an authenticated response. A retry always reaches Core using the
    current caller's credentials. A crash before COMMIT may leave orphan captures,
    but cannot dispatch an unjournaled checkpoint.
    """
    db = connect(directory)
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT fingerprint,args FROM requests WHERE key=?', (key,)).fetchone()
        if row:
            require(row[0] == digest(intent), 'idempotency_mismatch', 'Journal key reused for another intent')
            return json.loads(row[1])
        args = prepare()
        db.execute('INSERT INTO requests VALUES (?,?,?)', (key, digest(intent), canonical(args)))
        db.commit()
        return args
    finally:
        db.close()


PHASES = {'planning','inference','editing','calculation','waiting','capture','publication','review','restore'}


def start_span(directory, phase, state_id, operation, parent_id=None, entry_point='workflow_cli'):
    require(phase in PHASES, 'invalid_input', 'Unknown workflow phase')
    require(all(isinstance(v,str) and 0 < len(v) <= 200 for v in (state_id,operation,entry_point)),
            'invalid_input', 'Bounded state, operation and entry point required')
    db=connect(directory); span_id=uid('span')
    try:
        if parent_id:
            require(db.execute('SELECT 1 FROM spans WHERE id=?',(parent_id,)).fetchone(),
                    'not_found','Parent span must exist in this journal')
        metadata={'phase':phase,'state_id':state_id,'operation':operation,'parent_id':parent_id,
                  'entry_point':entry_point,'monotonic_start':time.monotonic()}
        db.execute('INSERT INTO spans VALUES (?,?,?,?,?,?)',
                   (span_id,canonical(metadata),time.time(),None,None,None)); db.commit()
        return span_id
    finally: db.close()


def transition(directory, span_id, action, outcome='completed'):
    require(action in {'pause','resume','finish'},'invalid_input','Unknown span transition')
    require(isinstance(outcome,str) and 0<len(outcome)<=100,'invalid_input','Bounded outcome code required')
    db=connect(directory)
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT metadata,started,ended,outcome FROM spans WHERE id=?',(span_id,)).fetchone()
        require(row,'not_found','Span missing'); metadata=json.loads(row[0])
        if action=='resume':
            require(row[3]=='paused' and not metadata.get('resumed_by'),'conflict','Only an unresumed pause can resume')
            next_id=uid('span'); metadata['resumed_by']=next_id
            db.execute('UPDATE spans SET metadata=? WHERE id=?',(canonical(metadata),span_id))
            new={k:v for k,v in metadata.items() if k not in {'resumed_by','monotonic_start'}}
            new.update(continuation_of=span_id,monotonic_start=time.monotonic())
            db.execute('INSERT INTO spans VALUES (?,?,?,?,?,?)',(next_id,canonical(new),time.time(),None,None,None))
            db.commit(); return next_id
        require(row[2] is None,'conflict','Span already closed')
        ended=time.time(); mono=time.monotonic()-metadata.get('monotonic_start',time.monotonic())
        duration=mono if mono>=0 and abs((ended-row[1])-mono)<=2 else None
        db.execute('UPDATE spans SET ended=?,seconds=?,outcome=? WHERE id=?',
                   (ended,duration,'paused' if action=='pause' else outcome,span_id)); db.commit()
        return span_id
    finally: db.close()


@contextmanager
def measure(directory, phase, state_id, operation, parent_id=None):
    span_id=start_span(directory,phase,state_id,operation,parent_id,'adapter')
    outcome='completed'
    try:
        yield span_id
    except BaseException as exc:
        outcome=getattr(exc,'code','interrupted' if not isinstance(exc,Exception) else 'error')
        raise
    finally:
        transition(directory,span_id,'finish',outcome)


def timing_report(directory):
    db=connect(directory)
    try: rows=db.execute('SELECT * FROM spans ORDER BY started,id LIMIT 10001').fetchall()
    finally: db.close()
    require(len(rows)<=10000,'acquisition_limit','Split timing journals by development session')
    spans=[{'id':r[0],'metadata':json.loads(r[1]),'started':r[2],'ended':r[3],'seconds':r[4],'outcome':r[5]} for r in rows]
    complete=[s for s in spans if s['seconds'] is not None]
    intervals=sorted((s['started'],s['started']+s['seconds']) for s in complete)
    merged=[]
    for a,b in intervals:
        if merged and a<=merged[-1][1]: merged[-1][1]=max(merged[-1][1],b)
        else: merged.append([a,b])
    phases={}
    for phase in sorted(PHASES):
        selected=[s for s in complete if s['metadata']['phase']==phase]
        durations=sorted(s['seconds'] for s in selected)
        if durations:
            import math
            phases[phase]={'count':len(durations),'summed_seconds':sum(durations),
                'p50_seconds':durations[math.ceil(.5*len(durations))-1],
                'p95_seconds':durations[math.ceil(.95*len(durations))-1]}
    return {'version':1,'spans':spans,'phases':phases,
        'measured_wall_seconds':sum(b-a for a,b in merged),
        'summed_span_seconds':sum(s['seconds'] for s in complete),
        'observed_elapsed_seconds':max((b for a,b in intervals),default=0)-min((a for a,b in intervals),default=0),
        'open_spans':sum(s['ended'] is None for s in spans),
        'unknown_duration_spans':sum(s['ended'] is not None and s['seconds'] is None for s in spans),
        'limitations':['Only instrumented local intervals; no historical reconstruction',
            'Summed spans include parallel/nested work; use interval union for measured wall time',
            'Clock discontinuities and unfinished spans are unknown, not zero-cost work',
            'Separate host timelines must not be merged without clock alignment']}
