"""Content-addressed persistent treap for immutable file manifests.

Nodes are shared across revisions. Updating k known paths stores expected
O(k log N) nodes; an incoming full manifest still costs O(N) to compare.
Physical storage encoding is private; API/export/event hashes use logical JSON.
"""
import copy
import hashlib
import json
from .model import canonical, digest, require


def schema(con):
    con.executescript('''
      CREATE TABLE IF NOT EXISTS manifest_nodes(hash TEXT PRIMARY KEY, body TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS manifest_roots(fingerprint TEXT PRIMARY KEY, root TEXT, file_count INTEGER);
      CREATE TABLE IF NOT EXISTS manifest_recent(id INTEGER PRIMARY KEY CHECK(id=1), root TEXT);
      CREATE TABLE IF NOT EXISTS artifact_roots(revision_id TEXT PRIMARY KEY, root TEXT);
    ''')
    if 'file_count' not in {r[1] for r in con.execute('PRAGMA table_info(manifest_roots)')}:
        con.execute('ALTER TABLE manifest_roots ADD COLUMN file_count INTEGER')
    con.execute('CREATE INDEX IF NOT EXISTS manifest_counts ON manifest_roots(file_count)')


class Tree:
    def __init__(self,con): self.con=con;self.cache={}
    def node(self,h):
        if h is None:return None
        if h not in self.cache:
            row=self.con.execute('SELECT body FROM manifest_nodes WHERE hash=?',(h,)).fetchone()
            require(row is not None,'integrity_error','Missing manifest node')
            value=json.loads(row[0]);require(digest(value)==h,'integrity_error','Corrupt manifest node');self.cache[h]=value
        return self.cache[h]
    def put(self,key,value,left=None,right=None):
        node=[key,value,left,right];h=digest(node)
        self.con.execute('INSERT OR IGNORE INTO manifest_nodes VALUES (?,?)',(h,canonical(node)));self.cache[h]=node;return h
    @staticmethod
    def priority(key):return hashlib.sha256(key.encode()).hexdigest(),key
    def merge(self,left,right):
        if left is None:return right
        if right is None:return left
        a=self.node(left);b=self.node(right)
        if self.priority(a[0])<self.priority(b[0]):return self.put(a[0],a[1],a[2],self.merge(a[3],right))
        return self.put(b[0],b[1],self.merge(left,b[2]),b[3])
    def update(self,root,key,value):
        if root is None:return self.put(key,value) if value is not None else None
        n=self.node(root);name,old,left,right=n
        if key==name:return self.merge(left,right) if value is None else root if value==old else self.put(key,value,left,right)
        if key<name:
            changed=self.update(left,key,value)
            if changed==left:return root
            c=self.node(changed)
            if c and self.priority(c[0])<self.priority(name):return self.put(c[0],c[1],c[2],self.put(name,old,c[3],right))
            return self.put(name,old,changed,right)
        changed=self.update(right,key,value)
        if changed==right:return root
        c=self.node(changed)
        if c and self.priority(c[0])<self.priority(name):return self.put(c[0],c[1],self.put(name,old,left,c[2]),c[3])
        return self.put(name,old,left,changed)
    def get(self,root,key):
        while root:
            n=self.node(root)
            if key==n[0]:return n[1]
            root=n[2] if key<n[0] else n[3]
        return None
    def items(self,root,after=''):
        if root:
            key,value,left,right=self.node(root)
            if key>after:
                yield from self.items(left,after);yield key,value
            yield from self.items(right,after)
    def manifest(self,files):
        fp=digest(files);row=self.con.execute('SELECT root FROM manifest_roots WHERE fingerprint=?',(fp,)).fetchone()
        if row:return row[0]
        lower=self.con.execute('SELECT MAX(file_count) FROM manifest_roots WHERE file_count<=?',(len(files),)).fetchone()[0]
        upper=self.con.execute('SELECT MIN(file_count) FROM manifest_roots WHERE file_count>=?',(len(files),)).fetchone()[0]
        counts=[n for n in (lower,upper) if n is not None]
        nearest=min(counts,key=lambda n:abs(n-len(files))) if counts else None
        row=self.con.execute('SELECT root FROM manifest_roots WHERE file_count=? ORDER BY rowid DESC LIMIT 1',(nearest,)).fetchone()
        root=row[0] if row else None
        old=dict(self.items(root))
        for name in sorted(set(old)|set(files)):
            if old.get(name)!=files.get(name):root=self.update(root,name,files.get(name))
        self.con.execute('INSERT INTO manifest_roots VALUES (?,?,?)',(fp,root,len(files)))
        self.con.execute('INSERT OR REPLACE INTO manifest_recent VALUES (1,?)',(root,))
        return root


def pack(con,value):
    tree=Tree(con)
    def visit(x):
        if isinstance(x,list):return [visit(v) for v in x]
        if not isinstance(x,dict):return x
        if x.get('type')=='artifact_snapshot' and isinstance(x.get('data',{}).get('files'),dict):
            y=copy.deepcopy(x);root=tree.manifest(y['data']['files'])
            y['data']['files']={'_manifest_root':root};return y
        return {k:visit(v) for k,v in x.items()}
    return {'_gantry_storage':1,'value':visit(value)}


def unpack(con,value):
    if '_gantry_storage' not in value:return value
    require(value['_gantry_storage']==1 and set(value)=={'_gantry_storage','value'},'unsupported_schema','Unknown physical record encoding')
    tree=Tree(con)
    def visit(x):
        if isinstance(x,list):return [visit(v) for v in x]
        if not isinstance(x,dict):return x
        if x.get('type')=='artifact_snapshot' and set(x.get('data',{}).get('files',{}))=={'_manifest_root'}:
            y=copy.deepcopy(x);y['data']['files']=dict(tree.items(y['data']['files']['_manifest_root']));return y
        return {k:visit(v) for k,v in x.items()}
    return visit(value['value'])


def file_info(con,revision,path):
    row=con.execute('SELECT root FROM artifact_roots WHERE revision_id=?',(revision,)).fetchone()
    return Tree(con).get(row[0],path) if row else None
