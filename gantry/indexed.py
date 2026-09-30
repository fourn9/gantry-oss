"""Transaction-local lazy record projection. Iteration is explicit full-table work."""
import copy
from . import manifest_store as manifests
import json
from collections.abc import MutableMapping


class Records(MutableMapping):
    def __init__(self, con, table):
        self.con, self.table, self.cache = con, table, {}

    def __getitem__(self, key):
        if key not in self.cache:
            row = self.con.execute('SELECT body FROM records WHERE collection=? AND id=?', (self.table, key)).fetchone()
            if row is None: raise KeyError(key)
            self.cache[key] = manifests.unpack(self.con,json.loads(row[0]))
        return self.cache[key]

    def __setitem__(self, key, value): self.cache[key] = value
    def __delitem__(self, key): raise TypeError('Projection records are replaced, not deleted')
    def __iter__(self):
        keys = {row[0] for row in self.con.execute('SELECT id FROM records WHERE collection=?', (self.table,))}
        return iter(sorted(keys | self.cache.keys()))
    def __len__(self): return sum(1 for _ in self)
    def __deepcopy__(self, memo): return {k: copy.deepcopy(self[k], memo) for k in self}


def schema(con):
    manifests.schema(con)
    con.executescript('''
      CREATE TABLE IF NOT EXISTS records(
        collection TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
        session_id TEXT, state_id TEXT, subject_id TEXT, profile TEXT, created_seq INTEGER,
        PRIMARY KEY(collection,id));
      CREATE INDEX IF NOT EXISTS records_by_session ON records(collection,session_id,id);
      CREATE INDEX IF NOT EXISTS evidence_by_state ON records(collection,state_id,id);
      CREATE INDEX IF NOT EXISTS evidence_by_subject ON records(collection,state_id,subject_id,id);
      CREATE INDEX IF NOT EXISTS evidence_by_profile ON records(collection,state_id,profile,id);
      CREATE TABLE IF NOT EXISTS artifact_file_index(
        revision_id TEXT NOT NULL, path TEXT NOT NULL, body TEXT NOT NULL,
        PRIMARY KEY(revision_id,path));
    ''')


def put(con, table, key, value, canonical):
    con.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?,?,?,?,?)',
        (table, key, canonical(manifests.pack(con,value)), value.get('session_id'), value.get('state_id'),
         value.get('subject_id'), value.get('profile'), value.get('created_seq')))
    if table == 'principals':
        con.execute('DELETE FROM credentials WHERE actor=?', (key,))
        if value.get('enabled', True):
            con.execute('INSERT OR REPLACE INTO credentials VALUES (?,?)', (value['token_hash'], key))
    if table == 'revisions' and value.get('type') == 'artifact_snapshot':
        root=manifests.Tree(con).manifest(value['data']['files'])
        con.execute('INSERT OR REPLACE INTO artifact_roots VALUES (?,?)',(key,root))


def header(state):
    return {'_indexed': 2, 'head': state.get('head'), 'ledger_id': state['ledger_id'],
            'seq': state['seq'], 'collections': sorted(k for k in state if k not in {'head','ledger_id','seq'})}


def rebuild(con, state, canonical):
    con.execute('DELETE FROM credentials')
    con.execute('DELETE FROM records'); con.execute('DELETE FROM artifact_file_index'); con.execute('DELETE FROM artifact_roots')
    for table in header(state)['collections']:
        for key, value in state[table].items(): put(con, table, key, value, canonical)
    con.execute('INSERT OR REPLACE INTO projection VALUES (1,?)', (canonical(header(state)),))


def load(con, meta):
    return {**{k: Records(con, k) for k in meta['collections']},
            **{k: meta[k] for k in ('head','seq','ledger_id')}}
