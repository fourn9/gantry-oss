"""Pure, bounded evidence views of operator-selected organizational exports.

Callers retain the original bytes and enforce storage/access/credential policy.
This module never opens paths, fetches links, extracts ZIPs or evaluates formulas.
Records are source observations, not approved roles, policies or authority grants.
"""
import csv
import hashlib
import io
import json
import posixpath
import re
import stat
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import PurePosixPath

from .connection_policy import MAX_FILE, clean_bytes
from .model import Fault, digest, require

MAX_SOURCE_BYTES = MAX_FILE
MAX_TEXT = 120000
MAX_RECORDS = 500
MAX_XLSX_MEMBERS = 1024
MAX_XLSX_EXPANDED = 32 * 1024 * 1024
MAX_XLSX_MEMBER = 4 * 1024 * 1024
MAX_XLSX_CELLS = 20000
S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


class _View:
    def __init__(self, path, raw, provider):
        self.result = {'provider': provider, 'path': path,
                       'hash': hashlib.sha256(raw).hexdigest(), 'records': [], 'limitations': []}
        self.remaining = MAX_TEXT

    def limit(self, message):
        if message not in self.result['limitations']:
            self.result['limitations'].append(message)

    def add(self, locator, text):
        _check_secret(text)
        if len(self.result['records']) >= MAX_RECORDS or not self.remaining:
            self.limit('Additional source content omitted: evidence record or text limit reached.')
            return False
        if len(text) > self.remaining:
            text = text[:self.remaining]
            self.limit('Source text omitted after the evidence text limit; the last record is truncated.')
        self.remaining -= len(text)
        source = self.result
        source['records'].append({'id': digest([source['path'], source['hash'], locator]),
            'path': source['path'], 'hash': source['hash'], 'locator': locator,
            'text': text, 'kind': 'observed'})
        return True


def _check_secret(text):
    clean_bytes(text.encode('utf-8'))


def _decode(raw):
    try:
        text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeError:
        raise Fault('invalid_input', 'Export must be UTF-8 text or BOM-marked UTF-16 text') from None
    require('\0' not in text, 'invalid_input', 'Binary data is not a supported text export')
    _check_secret(text)
    return text


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'invalid_input', 'Duplicate JSON keys would lose source evidence')
        result[key] = value
    return result


def _json_view(view, text):
    try:
        value = json.loads(text, object_pairs_hook=_json_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        _check_secret(_json_text(value))
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                for key, child in item.items():
                    if isinstance(child, str):
                        _check_secret(key + '=' + child)
                    pending.append(child)
            elif isinstance(item, list):
                pending.extend(item)
        if isinstance(value, list):
            rows = ((f'json:/{i}', item) for i, item in enumerate(value))
        elif isinstance(value, dict):
            rows = (('json:/' + key.replace('~', '~0').replace('/', '~1'), {key: item})
                    for key, item in value.items())
        else:
            rows = [('json:', value)]
        for locator, item in rows:
            if not view.add(locator, _json_text(item)):
                break
    except (ValueError, RecursionError):
        raise Fault('invalid_input', 'Malformed, non-finite or excessively nested JSON export') from None


def _csv_view(view, text):
    view.limit('CSV values are source text; formulas are not evaluated.')
    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        columns = next(reader, None)
        if columns is None:
            return
        require(len(columns) <= 10000, 'acquisition_limit', 'CSV column count exceeds safe limit')
        cells = len(columns)
        found = False
        for number, values in enumerate(reader, 2):
            found = True
            cells += len(values)
            require(number <= 100000 and cells <= 200000, 'acquisition_limit', 'CSV row or cell count exceeds safe limit')
            for key, value in zip(columns, values):
                _check_secret(key + '=' + value)
            if len(columns) != len(values):
                view.limit('CSV row widths differ from the header; all selected values are retained.')
            view.add(f'csv:row:{number}', _json_text({'columns': columns, 'values': values}))
        if not found:
            view.add('csv:row:1', _json_text({'columns': columns, 'values': []}))
    except csv.Error:
        raise Fault('invalid_input', 'Malformed CSV or field exceeds safe parsing limit') from None


class _BoundedXML(ET.TreeBuilder):
    def __init__(self, budget):
        super().__init__()
        self.depth = 0
        self.budget = budget

    def start(self, tag, attributes):
        self.depth += 1
        self.budget[0] += 1
        require(self.depth <= 64 and self.budget[0] <= 200000, 'acquisition_limit',
                'Workbook XML depth or element count exceeds safe limits')
        return super().start(tag, attributes)

    def end(self, tag):
        self.depth -= 1
        return super().end(tag)


def _workbook_documents(raw):
    documents = {}
    budget = [0]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(len(infos) <= MAX_XLSX_MEMBERS and
                sum(info.file_size for info in infos) <= MAX_XLSX_EXPANDED,
                'acquisition_limit', 'Workbook member count or expanded size exceeds safe limits')
        require(len({info.filename.casefold() for info in infos}) == len(infos),
                'invalid_input', 'Duplicate workbook members')
        for info in infos:
            name = info.filename
            parts = name.rstrip('/').split('/')
            require(name == info.orig_filename and len(name) <= 512 and
                    all(part not in {'', '.', '..'} for part in parts) and
                    not any(c in name for c in ('\\', ':', '\0')) and
                    not stat.S_ISLNK(info.external_attr >> 16), 'invalid_input', 'Unsafe workbook member path')
            lower = name.lower()
            require(not info.flag_bits & 1, 'unsupported', 'Encrypted workbooks are unsupported')
            require(info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED},
                    'unsupported', 'Unsupported workbook compression')
            require(info.file_size <= MAX_XLSX_MEMBER and
                    info.file_size <= max(1, info.compress_size) * 200,
                    'acquisition_limit', 'Workbook member expansion exceeds safe limits')
            require(not any(part in lower for part in
                    ('vbaproject', 'macrosheet', 'dialogsheet', 'externallinks/', 'embeddings/', 'activex/')),
                    'unsupported', 'Macros, external links and embedded objects are unsupported')
            if info.is_dir():
                continue
            # Conservative XML-only subset: binary attachments can hide active content.
            require(lower.endswith(('.xml', '.rels')), 'unsupported',
                    'Use an XLSX export without binary attachments, images or embedded content')
            with archive.open(info) as member:
                payload = member.read(MAX_XLSX_MEMBER + 1)
            require(len(payload) == info.file_size and len(payload) <= MAX_XLSX_MEMBER,
                    'acquisition_limit', 'Workbook member size does not match safe bounds')
            clean_bytes(payload)
            require(b'\0' not in payload and b'<!DOCTYPE' not in payload.upper() and
                    b'<!ENTITY' not in payload.upper(), 'invalid_input',
                    'Workbook XML must be UTF-8 without DTDs or entity declarations')
            text = payload.decode('utf-8-sig')
            _check_secret(text)
            root = ET.fromstring(text, parser=ET.XMLParser(target=_BoundedXML(budget)))
            _check_secret(''.join(root.itertext()))
            for element in root.iter():
                attributes = {key.rsplit('}', 1)[-1].lower(): value for key, value in element.attrib.items()}
                for value in attributes.values():
                    _check_secret(value)
                require(not any(word in value.lower() for value in attributes.values()
                                for word in ('macroenabled', 'vbaproject', 'macrosheet', 'oleobject', 'activex', 'externallink')),
                        'unsupported', 'Active workbook content is unsupported')
                if element.tag.rsplit('}', 1)[-1] == 'Relationship':
                    target = attributes.get('target', '')
                    require(attributes.get('targetmode', '').lower() != 'external' and
                            not re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) and
                            not target.startswith('//') and '\\' not in target,
                            'scope_denied', 'External workbook relationships are unsupported')
            documents[name] = root
    return documents


def _stored_cell(cell, shared, view):
    if cell.find(S + 'f') is not None:
        view.limit('Formula cells and their unverified cached results are omitted; formulas are never evaluated.')
        return None
    kind = cell.get('t', 'n')
    value = cell.findtext(S + 'v')
    if kind == 's' and value is not None:
        require(value.isdecimal() and int(value) < len(shared), 'invalid_input', 'Invalid shared string index')
        value = shared[int(value)]
    elif kind == 'inlineStr':
        value = ''.join(node.text or '' for node in cell.findall('.//' + S + 't'))
    require(kind in {'s', 'inlineStr', 'str', 'n', 'b', 'e', 'd'}, 'unsupported', 'Unsupported workbook cell type')
    return value


def _xlsx_view(view, raw):
    view.limit('Only stored worksheet cell values are evidence; formatting, date display, charts, comments and other workbook metadata are omitted.')
    try:
        documents = _workbook_documents(raw)
        book = documents['xl/workbook.xml']
        require(book.tag == S + 'workbook', 'unsupported', 'Unsupported workbook XML namespace')
        relationships = {}
        for relation in documents['xl/_rels/workbook.xml.rels']:
            key = relation.attrib['Id']
            require(key not in relationships, 'invalid_input', 'Duplicate workbook relationship IDs')
            relationships[key] = relation.attrib['Target']
        shared = [''.join(node.text or '' for node in item.findall('.//' + S + 't'))
                  for item in documents.get('xl/sharedStrings.xml', ET.Element('empty')).findall(S + 'si')]
        require(len(shared) <= MAX_XLSX_CELLS, 'acquisition_limit', 'Workbook shared string count exceeds limit')
        sheet_names = set()
        cells_seen = 0
        for sheet in book.findall(S + 'sheets/' + S + 'sheet'):
            name = sheet.attrib['name']
            require(name not in sheet_names and 0 < len(name) <= 255,
                    'invalid_input', 'Duplicate or invalid worksheet names')
            sheet_names.add(name)
            _check_secret(name)
            target = relationships[sheet.attrib[R + 'id']]
            target = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
            require(target.startswith('xl/worksheets/'), 'scope_denied', 'Worksheet target escapes workbook sheets')
            worksheet = documents[target]
            require(worksheet.tag == S + 'worksheet', 'invalid_input', 'Worksheet XML required')
            seen_addresses = set()
            seen_rows = set()
            headers = {}; previous_row = {}
            for index, row in enumerate(worksheet.findall(S + 'sheetData/' + S + 'row'), 1):
                number = row.get('r', str(index))
                require(number.isdecimal() and 1 <= int(number) <= 1048576 and number not in seen_rows,
                        'invalid_input', 'Invalid or duplicate worksheet row')
                seen_rows.add(number)
                values = {}; column_values = {}
                for cell in row.findall(S + 'c'):
                    cells_seen += 1
                    require(cells_seen <= MAX_XLSX_CELLS, 'acquisition_limit', 'Workbook cell count exceeds safe limit')
                    address = cell.get('r', '')
                    match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', address)
                    require(match and int(match[2]) == int(number) and address not in seen_addresses,
                            'invalid_input', 'Invalid or duplicate workbook cell address')
                    column = 0
                    for letter in match[1]:
                        column = column * 26 + ord(letter) - ord('A') + 1
                    require(column <= 16384, 'invalid_input', 'Workbook cell address exceeds column limit')
                    seen_addresses.add(address)
                    value = _stored_cell(cell, shared, view)
                    if value is not None:
                        _check_secret(value)
                        values[address] = value
                        column_values[column] = value
                # A credential may be split across a header/value column or an
                # adjacent label/value pair; inspect these before output truncation.
                for column,value in column_values.items():
                    for label in (headers.get(column),previous_row.get(column),column_values.get(column-1)):
                        if label is not None:_check_secret(label+'='+value)
                    headers.setdefault(column,value)
                previous_row=column_values
                if values:
                    view.add(f'xlsx:{name}!row:{number}', _json_text(values))
        require(sheet_names, 'invalid_input', 'Workbook contains no supported worksheets')
    except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError, UnicodeError,
            IndexError, EOFError, RuntimeError, NotImplementedError, zlib.error):
        raise Fault('invalid_input', 'Malformed or unsupported XLSX; no evidence was published') from None


def parse_source(path: str, raw: bytes, provider: str = 'generic') -> dict:
    """Return <=500 records / <=120,000 text characters, with explicit omissions.

    Unsafe, malformed and unsupported inputs raise ``Fault``. Locators identify
    source lines, CSV rows, JSON pointers, or workbook sheet rows; record IDs bind
    the exact source path, original SHA-256 hash and locator. Provider is a label.
    """
    require(isinstance(path, str) and 0 < len(path) <= 1024 and '\0' not in path,
            'invalid_input', 'Source path must be a nonempty bounded label')
    require(isinstance(provider, str) and 0 < len(provider) <= 80,
            'invalid_input', 'Source provider must be a bounded label')
    require(isinstance(raw, bytes), 'invalid_input', 'Original source bytes required')
    require(len(raw) <= MAX_SOURCE_BYTES, 'acquisition_limit', 'Source exceeds 16 MiB; export a smaller selection')
    clean_bytes(raw)
    suffix = PurePosixPath(path).suffix.lower()
    require(suffix != '.xls', 'unsupported', 'Native .xls is unsupported; export as CSV or a safe .xlsx workbook')
    require(suffix in {'.md', '.markdown', '.txt', '.text', '.csv', '.json', '.xlsx'},
            'unsupported', 'Use Markdown, text, CSV, JSON or a safe .xlsx export; archives are not imported')
    view = _View(path, raw, provider)
    if suffix == '.xlsx':
        _xlsx_view(view, raw)
    else:
        text = _decode(raw)
        if suffix == '.json':
            _json_view(view, text)
        elif suffix == '.csv':
            _csv_view(view, text)
        else:
            for line, content in enumerate(io.StringIO(text, newline=''), 1):
                if not view.add(f'line:{line}', content):
                    break
    if not view.result['records']:
        view.limit('No source records available in this export.')
    return view.result
