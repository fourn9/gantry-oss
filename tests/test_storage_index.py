import base64
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch
import test_development as fixture
from gantry import manifest_store,indexed
from gantry.service import Service
from gantry.model import canonical

class StorageTests(unittest.TestCase):
    setUp=fixture.DevelopmentTests.setUp;tearDown=fixture.DevelopmentTests.tearDown
    call=fixture.DevelopmentTests.call;artifact=fixture.DevelopmentTests.artifact
    policy=fixture.DevelopmentTests.policy;connect=fixture.DevelopmentTests.connect
    def test_historical_manifests_share_nodes_and_random_lookup_avoids_state_scan(self):
        files={'parts/%04d.step'%i:'same'+str(i) for i in range(999)}
        first=self.artifact(files)
        with self.service.store.connect() as con:initial=con.execute('SELECT count(*) FROM manifest_nodes').fetchone()[0]
        roots=[]
        for version in range(8):
            files['parts/0500.step']='changed'+str(version);roots.append(self.artifact(files))
        files['parts/new.step']='new part';roots.append(self.artifact(files))
        with self.service.store.connect() as con:
            added=con.execute('SELECT count(*) FROM manifest_nodes').fetchone()[0]-initial
            self.assertLess(added,400) # Eight edits must not copy 8,000 manifest entries.
            event=json.loads(con.execute('SELECT body FROM events ORDER BY seq DESC LIMIT 1').fetchone()[0])
            self.assertLess(len(canonical(event)),15000)
        with patch.object(indexed.Records,'__iter__',side_effect=AssertionError('Full table scan')):
            got=self.call('read_artifact_chunk',{'revision_id':roots[-1],'path':'parts/0500.step','index':0})
        self.assertEqual(base64.b64decode(got['content']),b'changed7')
        original=self.call('read_artifact_chunk',{'revision_id':first,'path':'parts/0500.step','index':0})
        self.assertEqual(base64.b64decode(original['content']),b'same500')
        self.assertTrue(self.call('replay')['matched'])

    def test_legacy_projection_migrates_without_changing_event_bytes(self):
        with self.service.store.connect() as con:
            logical=self.service.store.state(con,2)
            before=list(con.execute('SELECT seq,body FROM events ORDER BY seq'))
            con.execute('UPDATE projection SET body=?',(canonical(logical),))
        fresh=Service(self.service.store.directory)
        with fresh.store.connect() as con:
            after=list(con.execute('SELECT seq,body FROM events ORDER BY seq'))
            self.assertEqual([tuple(x) for x in before],[tuple(x) for x in after])
            self.assertEqual(json.loads(con.execute('SELECT body FROM projection').fetchone()[0])['_indexed'],2)
        self.assertTrue(fresh.call(self.token,'verify')['valid'])
