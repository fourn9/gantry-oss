"""Read saved active native documents via customer-local Windows Automation.

Experimental, not validated against installed vendor products. Never launches,
opens, saves, closes or edits a vendor document. No arbitrary COM method dispatch.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from .model import require, digest, Fault
from .vendor_bridge import load, read_safe, safe_path


def inspect_active(product, app):
    if product=='solidworks':
        doc=app.ActiveDoc
        require(doc is not None,'not_found','No active SOLIDWORKS document')
        return {'path':doc.GetPathName(),'dirty':bool(doc.GetSaveFlag()),'version':app.RevisionNumber()}
    if product=='catia-v5':
        doc=app.ActiveDocument;cfg=app.SystemConfiguration
        return {'path':doc.FullName,'dirty':not bool(doc.Saved),
                'version':f'{cfg.Version}.{cfg.Release}.{cfg.ServicePack}'}
    raise Fault('unsupported_operation','Native driver is not implemented for this product')


def capture_active(bundle, app):
    root=Path(bundle);request=load(root,'request.json')
    require(request.get('operation')=='capture','unsupported_operation','Read-only capture required')
    require(digest({k:v for k,v in request.items() if k!='request_hash'})==request['request_hash'],'integrity_error','Request changed')
    require(not (root/'result.json').exists(),'conflict','Result already exists; do not overwrite')
    require(not (root/'output').is_symlink() and not any((root/'output').iterdir()),'conflict','Output must be empty')
    first=inspect_active(request['product'],app)
    require(first['version']==request['version'],'stale_basis','Vendor version differs from request')
    require(first['path'] and not first['dirty'],'capture_incomplete','Save the staged document before capture')
    active=Path(first['path']).resolve();inputs=request['inputs']
    require(isinstance(inputs,dict) and 0<len(inputs)<=1000,'invalid_input','Invalid input manifest')
    name=next((n for n in inputs if safe_path(root/'input',n).resolve()==active),None)
    require(name is not None,'scope_denied','Active document must be an explicitly staged input')
    files={};content={};total=0
    for n,h in inputs.items():
        raw=read_safe(root/'input',n);total+=len(raw)
        require(total<=256*1024*1024,'invalid_input','Bundle exceeds 256 MiB')
        require(hashlib.sha256(raw).hexdigest()==h,'stale_basis','Staged input changed; prepare a new bundle')
        content[n]=raw;files[n]=h
    require(inspect_active(request['product'],app)==first,'stale_basis','Active document changed during capture')
    # Every saved dependency must be explicitly selected; no automatic traversal.
    for n,raw in content.items():
        p=safe_path(root/'output',n);p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    result={k:request[k] for k in ['schema_version','request_id','request_hash','product','version','operation']}
    result.update(status='completed',files=files,observations=[{'kind':'document','source_id':name,'source_path':name,
        'attributes':{'saved':True,'native_api_observed':True}}],coverage={
        'captured':['explicit saved input files','active document saved flag','application version'],
        'missing':['unselected dependencies','feature tree','assembly hierarchy','unsaved edits','physical verification'],
        'inferred':[]})
    with (root/'result.json').open('x') as f:json.dump(result,f,indent=2)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True);a=p.parse_args()
    req=load(a.bundle,'request.json');product=req['product']
    require(product in {'solidworks','catia-v5'},'unsupported_operation','Vendor SDK implementation required')
    require(sys.platform=='win32','platform_unavailable','Windows and installed licensed CAD required')
    try:
        import win32com.client
    except ImportError:raise Fault('dependency_missing','Install pywin32 in the customer Windows environment') from None
    try:
        app=win32com.client.GetActiveObject({'solidworks':'SldWorks.Application','catia-v5':'CATIA.Application'}[product])
        print(json.dumps(capture_active(a.bundle,app),indent=2))
    except Fault:raise
    except Exception:raise Fault('vendor_unavailable','Check active document, vendor API and installation locally') from None

if __name__=='__main__':main()
