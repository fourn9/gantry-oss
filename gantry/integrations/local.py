"""Read saved native exports and selected XLSX cells; never evaluate formulas/macros."""
import io
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from ..continuity_adapter import SECRET
from ..model import Fault, require
from .bundle import read_file, make_bundle, MAX_TOTAL, safe_file

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def xlsx_cells(raw,selection):
    require(isinstance(selection,dict) and 1<=len(selection)<=50,'invalid_input','Select worksheet names and cell addresses')
    require(sum(len(v) for v in selection.values())<=1000,'acquisition_limit','Select at most 1000 cells')
    for sheet,cells in selection.items():
        require(isinstance(sheet,str) and isinstance(cells,list) and all(isinstance(c,str) and
                re.fullmatch('[A-Z]{1,3}[1-9][0-9]{0,6}',c) for c in cells),'invalid_input','Cell list required')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            require(len(infos)<=2000 and sum(i.file_size for i in infos)<=MAX_TOTAL,'acquisition_limit','Workbook expansion exceeds limit')
            require(len({i.filename for i in infos})==len(infos),'invalid_input','Duplicate workbook members')
            payload={}
            for i in infos:
                safe_file(i.filename.rstrip('/'))
                require(not i.flag_bits&1 and 'vbaProject' not in i.filename,'unsupported','Encrypted or macro workbook is not supported')
                data=z.read(i)
                require(not SECRET.search(data),'credential_detected','Potential credential in workbook')
                if i.filename.endswith('.xml') or i.filename.endswith('.rels'):
                    require(b'\x00' not in data and b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper(),
                            'invalid_input','Only UTF-8 XML without entities is supported')
                payload[i.filename]=data
            def xml(name): return ET.fromstring(payload[name])
            relationships={r.attrib['Id']:r.attrib for r in xml('xl/_rels/workbook.xml.rels')}
            shared=[]
            if 'xl/sharedStrings.xml' in payload:
                shared=[''.join(e.itertext()) for e in xml('xl/sharedStrings.xml').findall('s:si',NS)]
            result={}
            for s in xml('xl/workbook.xml').findall('s:sheets/s:sheet',NS):
                name=s.attrib['name']
                if name not in selection: continue
                rel=relationships[s.attrib['{'+NS['r']+'}id']]
                require(rel.get('TargetMode')!='External','scope_denied','External worksheet denied')
                target=rel['Target']; target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
                require(target.startswith('xl/'),'scope_denied','Worksheet path escape')
                values={}
                for c in xml(target).findall('.//s:sheetData/s:row/s:c',NS):
                    addr=c.attrib.get('r')
                    if addr not in selection[name]: continue
                    form=c.find('s:f',NS); value=c.find('s:v',NS); text=value.text if value is not None else None
                    kind=c.attrib.get('t','n')
                    if kind=='s' and text is not None: text=shared[int(text)]
                    if kind=='inlineStr': text=''.join(c.find('s:is',NS).itertext())
                    values[addr]={'availability':'captured','value':text,'type':kind,
                        'formula':form.text if form is not None else None,
                        'value_status':'unverified_cached_formula' if form is not None else 'stored_value'}
                result[name]={cell:values.get(cell,{'availability':'not_captured_or_blank'}) for cell in selection[name]}
            for name in selection: result.setdefault(name,{'availability':'sheet_not_captured'})
            return result
    except (zipfile.BadZipFile,ET.ParseError,KeyError,ValueError,IndexError):
        raise Fault('invalid_input','Unsupported or malformed XLSX; no cells were published') from None


def capture_exports(provider,source_id,root,names,refs,selectors=None,cells=None):
    require(isinstance(names,list) and 1<=len(names)<=100 and len(set(names))==len(names), 'invalid_input','Explicit distinct file paths required')
    files={};total=0
    for name in names:
        raw=read_file(root,name);total+=len(raw)
        require(total<=MAX_TOTAL,'acquisition_limit','Capture exceeds 32 MiB');files[name]=raw
    missing=['unsaved edits','tool operation history','native API connection','automatic verification']
    if cells is not None:
        require(provider=='excel' and len(files)==1 and names[0].lower().endswith('.xlsx'), 'invalid_input','Select one XLSX workbook')
        view=xlsx_cells(files[names[0]],cells)
        from ..model import canonical
        files['selected-cells.json']=canonical(view).encode()
        missing+=['formula recalculation','cells outside selection']
    return make_bundle(provider,source_id,files,refs,selectors,
        source={'kind':'operator_selected_saved_export'},missing=missing)
