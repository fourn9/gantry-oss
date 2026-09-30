"""Opt-in local aggregate metrics. No network sender, payloads or identifiers."""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from . import __version__
from .contracts import CONTRACTS
from .model import require

BUCKETS = ('lt_100ms', 'lt_1s', 'lt_10s', 'ge_10s')
RESULTS = ('success', 'denied', 'conflict', 'invalid_input', 'failure')


class UsageMetrics:
    def __init__(self, directory):
        self.root = Path(directory) / 'usage'
        self.db = self.root / 'aggregate.sqlite3'
        self.config = self.root / 'consent.json'

    def enabled(self):
        require(not self.root.is_symlink() and not self.config.is_symlink(), "invalid_input", "No metrics symlinks")
        if not self.config.is_file(): return False
        return json.loads(self.config.read_text()).get('local_collection') is True

    def configure(self, enabled):
        require(type(enabled) is bool, 'invalid_input', 'Explicit collection choice required')
        require(not self.root.is_symlink(), "invalid_input", "No metrics directory symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        require(not self.config.is_symlink() and not self.db.is_symlink(), 'invalid_input', 'No metrics symlinks')
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('CREATE TABLE IF NOT EXISTS counts(day TEXT, operation TEXT, outcome TEXT, bucket TEXT, n INTEGER, PRIMARY KEY(day,operation,outcome,bucket))')
            if not enabled: con.execute('DELETE FROM counts')
            con.commit()
        os.chmod(self.db, 0o600)
        raw = json.dumps({'version':1, 'local_collection':enabled, 'automatic_transmission':False})
        fd = os.open(self.config, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'w') as f: f.write(raw)
        return {'local_collection': enabled, 'automatic_transmission':False,
                'retention_days':30, 'deleted_local_counts':not enabled}

    def record(self, command, result, seconds):
        if command not in CONTRACTS or not self.enabled(): return
        require(not self.db.is_symlink(), 'invalid_input', 'No metrics symlink')
        outcome = ('success' if result is None else 'denied' if result in {'unauthorized','scope_denied'} else
                   'conflict' if result in {'conflict','stale_basis','idempotency_mismatch'} else
                   'invalid_input' if result=='invalid_input' else 'failure')
        bucket = BUCKETS[0 if seconds < .1 else 1 if seconds < 1 else 2 if seconds < 10 else 3]
        now = datetime.now(timezone.utc)
        with closing(sqlite3.connect(self.db, timeout=1)) as con:
            con.execute('DELETE FROM counts WHERE day < ?', ((now-timedelta(days=29)).date().isoformat(),))
            con.execute('INSERT INTO counts VALUES (?,?,?,?,1) ON CONFLICT(day,operation,outcome,bucket) DO UPDATE SET n=n+1',
                        (now.date().isoformat(),command,outcome,bucket))
            con.commit()

    def report(self):
        rows = []
        if self.db.exists() and self.enabled():
            require(not self.db.is_symlink(), 'invalid_input', 'No metrics symlink')
            cutoff = (datetime.now(timezone.utc)-timedelta(days=29)).date().isoformat()
            with closing(sqlite3.connect(self.db)) as con:
                rows = con.execute('SELECT operation,outcome,bucket,SUM(n) FROM counts WHERE day>=? GROUP BY operation,outcome,bucket ORDER BY operation,outcome,bucket',(cutoff,)).fetchall()
        # No dates, workspace IDs, usernames, paths, contents, errors or host metadata.
        metrics = [{'operation':x,'outcome':y,'latency':z,'count':n} for x,y,z,n in rows]
        report = {'schema':1, 'gantry_version':__version__, 'metrics':metrics}
        validate_report(report)
        return report


def validate_report(report):
    require(isinstance(report, dict) and set(report)=={'schema','gantry_version','metrics'} and report['schema']==1,
            'invalid_input', 'Not an aggregate usage report')
    import re
    require(isinstance(report['gantry_version'],str) and re.fullmatch(r'\d+\.\d+\.\d+',report['gantry_version']),
            'invalid_input', 'Invalid version')
    require(isinstance(report['metrics'],list) and len(report['metrics'])<=len(CONTRACTS)*20, 'invalid_input', 'Invalid metric list')
    for item in report['metrics']:
        require(isinstance(item,dict) and set(item)=={'operation','outcome','latency','count'},'invalid_input','Unknown metric fields')
        require(item['operation'] in CONTRACTS and item['outcome'] in RESULTS and item['latency'] in BUCKETS
                and type(item['count']) is int and 0 < item['count'] < 10**12, 'invalid_input','Invalid aggregate metric')


def summarize(reports):
    totals = {}
    for report in reports:
        validate_report(report)
        for item in report['metrics']:
            key=(item['operation'],item['outcome'],item['latency'])
            totals[key]=totals.get(key,0)+item['count']
    return {'reports':len(reports), 'metrics':[{'operation':a,'outcome':b,'latency':c,'count':n}
            for (a,b,c),n in sorted(totals.items())],
            'limitation':'Voluntary aggregate samples; duplicate exports cannot be identified. No claim of unique users or causal speedup.'}
