import sqlite3
import unittest

from gantry import indexed
from gantry.model import canonical


class TypedEntryTests(unittest.TestCase):
    def test_pending_changes_and_legacy_rows_override_persisted_types(self):
        with sqlite3.connect(':memory:') as con:
            indexed.schema(con)
            rows = [dict(id='a', type='design_document'),
                    dict(id='b', type='design_document'), dict(id='c', type='incident')]
            for row in rows:
                indexed.put(con, 'entries', row['id'], row, canonical)
            con.execute("UPDATE records SET body=? WHERE collection='entries' AND id='b'", (canonical(rows[1]),))
            table = indexed.Records(con, 'entries')
            table['a'] = dict(id='a', type='incident')
            table['c'] = dict(id='c', type='design_document')
            table['d'] = dict(id='d', type='design_document', retracted=True)
            self.assertEqual([r['id'] for r in indexed.entry_values(table, 'design_document')], ['b', 'c', 'd'])
            self.assertEqual(list(indexed.entry_values({r['id']:r for r in rows}, 'design_document')), rows[:2])
