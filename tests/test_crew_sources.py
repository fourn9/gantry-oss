"""Anonymous source fixtures: evidence fidelity, bounds and hostile inputs."""
import hashlib
import io
import json
import unittest
import warnings
import zipfile

from gantry.crew_sources import parse_source
from gantry.model import Fault

S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def workbook(rows=None, *, extra=None, relationships=None, compression=zipfile.ZIP_STORED):
    rows = rows if rows is not None else '<row r="1"><c r="A1" t="inlineStr"><is><t>role</t></is></c></row>'
    files = {
        'xl/workbook.xml': f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Org" r:id="r1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': relationships or '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{S}"><sheetData>{rows}</sheetData></worksheet>',
    }
    files.update(extra or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=compression) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return buffer.getvalue()


class SourceTests(unittest.TestCase):
    def test_notion_markdown_preserves_text_and_exact_provenance(self):
        raw = '# Team\n\nEngineers report to the lead.\n'.encode()
        parsed = parse_source('exports/team.md', raw, 'notion')
        self.assertEqual(parsed['provider'], 'notion')
        self.assertEqual(parsed['hash'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(''.join(r['text'] for r in parsed['records']), raw.decode())
        self.assertEqual(parsed, parse_source('exports/team.md', raw, 'notion'))
        for record in parsed['records']:
            self.assertEqual(record['path'], 'exports/team.md')
            self.assertEqual(record['hash'], parsed['hash'])
            self.assertEqual(record['kind'], 'observed')
            self.assertTrue(record['locator'])
        self.assertNotEqual(parsed['records'][0]['id'], parse_source('other.md', raw)['records'][0]['id'])
        self.assertNotEqual(parsed['records'][0]['id'], parse_source('exports/team.md', raw + b'x')['records'][0]['id'])

    def test_csv_keeps_human_columns_duplicates_and_formula_text(self):
        raw = b'team,role,reports_to,responsibilities,role\nPlatform,Engineer,Lead,=HYPERLINK("https://invalid.test"),Reviewer\n'
        for provider in ('generic', 'linear', 'jira'):
            with self.subTest(provider=provider):
                parsed = parse_source('org.csv', raw, provider)
                row = json.loads(parsed['records'][0]['text'])
                self.assertEqual(row['columns'], ['team', 'role', 'reports_to', 'responsibilities', 'role'])
                self.assertEqual(row['values'][-1], 'Reviewer')
                self.assertTrue(row['values'][3].startswith('=HYPERLINK'))
                self.assertIn('formula', ' '.join(parsed['limitations']).lower())

    def test_csv_multiline_cells_and_unequal_rows_are_not_lost(self):
        parsed = parse_source('org.csv', b'role,notes\nLead,"line one\nline two"\nEngineer,build,extra\n')
        self.assertEqual(json.loads(parsed['records'][0]['text'])['values'][1], 'line one\nline two')
        self.assertEqual(json.loads(parsed['records'][1]['text'])['values'][2], 'extra')
        self.assertIn('width', ' '.join(parsed['limitations']).lower())
        self.assertNotEqual(parsed['records'][0]['locator'], parsed['records'][1]['locator'])

    def test_json_preserves_nested_fields_and_pointer_locators(self):
        raw = b'{"team/name":{"reports_to":"Lead","responsibilities":["Review","Build"]},"notes":"draft"}'
        parsed = parse_source('org.json', raw)
        self.assertEqual(json.loads(parsed['records'][0]['text'])['team/name']['reports_to'], 'Lead')
        self.assertIn('team~1name', parsed['records'][0]['locator'])
        listed = parse_source('org.json', b'[{"role":"Lead"},{"role":"Engineer"}]')
        self.assertEqual(len(listed['records']), 2)
        self.assertEqual(json.loads(listed['records'][1]['text']), {'role': 'Engineer'})

    def test_duplicate_json_keys_nonfinite_values_and_malformed_sources_rejected(self):
        for raw in (b'{"role":1,"role":2}', b'{', b'[NaN]', b'[1e999]', b'[' * 2000):
            with self.subTest(raw=raw[:40]), self.assertRaises(Fault):
                parse_source('org.json', raw)
        with self.assertRaises(Fault):
            parse_source('org.csv', b'role\n"unterminated')

    def test_utf_bom_supported_binary_and_invalid_text_rejected(self):
        for raw in ('team\nLead'.encode('utf-16'), 'team\nLead'.encode('utf-8-sig')):
            self.assertEqual(''.join(r['text'] for r in parse_source('org.txt', raw)['records']), 'team\nLead')
        for raw in (b'zero\x00byte', b'\xffinvalid'):
            with self.subTest(raw=raw), self.assertRaises(Fault):
                parse_source('org.txt', raw)

    def test_bounded_records_and_text_explicitly_report_omissions(self):
        for path, raw in (
            ('org.txt', b'line\n' * 700),
            ('org.txt', b'x' * 150000),
            ('org.csv', b'role\n' + b'Engineer\n' * 700),
            ('org.json', json.dumps(['x' * 2000] * 700).encode()),
        ):
            with self.subTest(path=path, size=len(raw)):
                parsed = parse_source(path, raw)
                self.assertLessEqual(len(parsed['records']), 500)
                self.assertLessEqual(sum(len(r['text']) for r in parsed['records']), 120000)
                self.assertTrue(any('omitt' in limitation.lower() for limitation in parsed['limitations']))

    def test_empty_source_is_explicit_and_source_size_is_bounded(self):
        self.assertTrue(parse_source('org.txt', b'')['limitations'])
        with self.assertRaises(Fault):
            parse_source('org.txt', b'x' * (16 * 1024 * 1024 + 1))
        self.assertTrue(parse_source('org.txt', b'x' * (8 * 1024 * 1024 + 1))['records'])

    def test_native_xls_and_archives_require_explicit_conversion(self):
        with self.assertRaises(Fault) as error:
            parse_source('org.xls', b'old workbook')
        self.assertIn('CSV', error.exception.message)
        for name in ('org.zip', 'org.pdf', 'org.xlsm'):
            with self.subTest(name=name), self.assertRaises(Fault):
                parse_source(name, b'unsupported')

    def test_credential_patterns_in_decoded_text_are_rejected(self):
        for raw in (('api_key=' + 'z' * 40).encode(), ('api_key=' + 'z' * 40).encode('utf-16')):
            with self.subTest(encoding=raw[:4]), self.assertRaises(Fault) as error:
                parse_source('org.txt', raw)
            self.assertEqual(error.exception.code, 'credential_detected')

    def test_secrets_in_omitted_and_escaped_values_are_rejected_before_any_records_return(self):
        cases = [
            ('org.txt', b'line\n' * 600 + b'api_key=' + b'z' * 40),
            ('org.json', json.dumps(['safe'] * 600 + [{'api_key': 'z' * 40}]).encode()),
            ('org.json', b'"\\u0061pi_key=' + b'z' * 40 + b'"'),
            ('org.csv', b'api_key\n' + b'none\n' * 600 + b'z' * 40),
        ]
        for path, raw in cases:
            with self.subTest(path=path), self.assertRaises(Fault):
                parse_source(path, raw)

    def test_utf8_json_and_csv_with_very_many_columns_are_rejected_without_process_errors(self):
        for path, raw in [('org.json', b'"\\ud800"'), ('org.csv', b'col,' * 10001)]:
            with self.subTest(path=path), self.assertRaises(Fault):
                parse_source(path, raw)


class WorkbookTests(unittest.TestCase):
    def test_cells_preserve_shared_inline_numeric_and_human_column_evidence(self):
        rows = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>reports_to</t></is></c></row>'
                '<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2" t="inlineStr"><is><t>Lead</t></is></c><c r="C2"><v>42</v></c></row>')
        raw = workbook(rows, extra={'xl/sharedStrings.xml': f'<sst xmlns="{S}"><si><t>role</t></si><si><r><t>Eng</t></r><r><t>ineer</t></r></si></sst>'})
        parsed = parse_source('org.xlsx', raw, 'spreadsheet')
        self.assertEqual(len(parsed['records']), 2)
        first, second = [json.loads(record['text']) for record in parsed['records']]
        self.assertEqual(first, {'A1': 'role', 'B1': 'reports_to'})
        self.assertEqual(second, {'A2': 'Engineer', 'B2': 'Lead', 'C2': '42'})
        self.assertIn('Org', parsed['records'][1]['locator'])
        self.assertEqual(parsed['hash'], hashlib.sha256(raw).hexdigest())

    def test_formulas_and_cached_results_omitted_explicitly(self):
        rows = '<row r="1"><c r="A1"><v>3</v></c><c r="B1"><f>HYPERLINK("https://invalid.test")</f><v>6</v></c></row>'
        parsed = parse_source('org.xlsx', workbook(rows))
        self.assertEqual(json.loads(parsed['records'][0]['text']), {'A1': '3'})
        self.assertIn('formula', ' '.join(parsed['limitations']).lower())
        self.assertIn('omitt', ' '.join(parsed['limitations']).lower())

    def test_doctype_entity_utf16_and_malformed_xml_rejected_anywhere(self):
        for xml in ('<!DOCTYPE x [<!ENTITY e "bad">]><x>&e;</x>', '<!ENTITY e "bad">', '<bad',
                    '<!DOCTYPE x><x/>'.encode('utf-16')):
            with self.subTest(xml=xml), self.assertRaises(Fault):
                parse_source('org.xlsx', workbook(extra={'unused.xml': xml}))

    def test_external_relationships_and_macros_rejected_anywhere(self):
        entries = [
            {'unused.rels': '<Relationships><Relationship TargetMode="External" Target="https://invalid.test"/></Relationships>'},
            {'xl/vbaProject.bin': b'macro'},
            {'xl/externalLinks/externalLink1.xml': '<x/>'},
            {'xl/embeddings/object.bin': b'object'},
            {'[Content_Types].xml': '<Types><Override ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/></Types>'},
        ]
        for extra in entries:
            with self.subTest(extra=extra), self.assertRaises(Fault):
                parse_source('org.xlsx', workbook(extra=extra))
        with self.assertRaises(Fault):
            parse_source('org.xlsx', workbook(relationships='<Relationships><Relationship Id="r1" Target="https://invalid.test/sheet.xml"/></Relationships>'))

    def test_zip_traversal_duplicate_members_and_invalid_zip_rejected(self):
        for name in ('../outside.xml', '/outside.xml', 'xl/../outside.xml', 'xl\\bad.xml'):
            with self.subTest(name=name), self.assertRaises(Fault):
                parse_source('org.xlsx', workbook(extra={name: '<x/>'}))
        raw = io.BytesIO(workbook())
        with warnings.catch_warnings(), zipfile.ZipFile(raw, 'a') as archive:
            warnings.simplefilter('ignore', UserWarning)
            archive.writestr('xl/workbook.xml', '<x/>')
        with self.assertRaises(Fault):
            parse_source('org.xlsx', raw.getvalue())
        with self.assertRaises(Fault):
            parse_source('org.xlsx', b'PK-not-a-zip')

    def test_zip_expansion_and_member_count_are_bounded(self):
        for raw in (
            workbook(extra={'huge.xml': '<x>' + 'a' * 300000 + '</x>'}, compression=zipfile.ZIP_DEFLATED),
            workbook(extra={f'extra{i}.xml': '<x/>' for i in range(1025)}),
        ):
            with self.subTest(size=len(raw)), self.assertRaises(Fault) as error:
                parse_source('org.xlsx', raw)
            self.assertEqual(error.exception.code, 'acquisition_limit')

    def test_cell_count_and_xml_depth_are_bounded_before_publication(self):
        for raw in (
            workbook(''.join(f'<row r="{i}"><c r="A{i}"><v>1</v></c></row>' for i in range(1, 20002))),
            workbook(extra={'deep.xml': '<x>' * 70 + '</x>' * 70}),
        ):
            with self.subTest(size=len(raw)), self.assertRaises(Fault):
                parse_source('org.xlsx', raw)

    def test_invalid_shared_index_duplicate_cells_and_outside_sheet_target_rejected(self):
        cases = [workbook('<row r="1"><c r="A1" t="s"><v>-1</v></c></row>'),
                 workbook('<row r="1"><c r="A1"><v>1</v></c><c r="A1"><v>2</v></c></row>'),
                 workbook(relationships='<Relationships><Relationship Id="r1" Target="../../outside.xml"/></Relationships>')]
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(Fault):
                parse_source('org.xlsx', raw)

    def test_xlsx_omissions_and_compressed_credentials_are_explicit(self):
        rows = ''.join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c></row>' for i in range(1, 601))
        parsed = parse_source('org.xlsx', workbook(rows))
        self.assertEqual(len(parsed['records']), 500)
        self.assertTrue(any('omitt' in message.lower() for message in parsed['limitations']))
        rows = '<row r="1"><c r="A1" t="inlineStr"><is><t>api_key=' + 'z' * 40 + '</t></is></c></row>'
        with self.assertRaises(Fault) as error:
            parse_source('org.xlsx', workbook(rows, compression=zipfile.ZIP_DEFLATED))
        self.assertEqual(error.exception.code, 'credential_detected')

    def test_spreadsheet_header_and_adjacent_label_secrets_rejected(self):
        cell=lambda address,text:f'<c r="{address}" t="inlineStr"><is><t>{text}</t></is></c>'
        cases=[f'<row r="1">{cell("A1","api_key")}</row><row r="2">{cell("A2","z"*40)}</row>',
               f'<row r="1">{cell("A1","api_key")}{cell("B1","z"*40)}</row>',
               f'<row r="1">{cell("A1","name")}</row><row r="500">{cell("A500","api_key")}</row><row r="501">{cell("A501","z"*40)}</row>']
        for rows in cases:
            with self.subTest(rows=rows[:50]),self.assertRaises(Fault) as error:
                parse_source('roles.xlsx',workbook(rows,compression=zipfile.ZIP_DEFLATED))
            self.assertEqual(error.exception.code,'credential_detected')
        benign=f'<row r="1">{cell("A1","api_key")}</row><row r="2">{cell("A2","not configured")}</row>'
        self.assertEqual(len(parse_source('roles.xlsx',workbook(benign))['records']),2)

    def test_secret_in_unreferenced_shared_string_after_evidence_limit_is_rejected(self):
        rows = ''.join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c></row>' for i in range(1, 601))
        shared = f'<sst xmlns="{S}"><si><t>api_</t><r><t>key=' + 'z' * 40 + '</t></r></si></sst>'
        with self.assertRaises(Fault) as error:
            parse_source('org.xlsx', workbook(rows, extra={'xl/sharedStrings.xml': shared}))
        self.assertEqual(error.exception.code, 'credential_detected')


if __name__ == '__main__':
    unittest.main()
