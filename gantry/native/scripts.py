"""Inspectable, single-use native host scripts. No unattended host launch or saved-pass claim."""
import hashlib
import json
import re
import secrets
from pathlib import Path
from ..model import canonical, digest, require
from ..integrations.bundle import make_bundle,write_bundle,read_bundle,read_file,safe_file
from ..integrations.transport import parse_json
from .workflow import root_path,root_identity


def literal(text,language):
    require(isinstance(text,str) and all(32<=ord(c)<127 for c in text),
            'unsupported','Initial native script route requires printable ASCII values and paths')
    return "'"+text.replace("'","''")+"'" if language=='pascal' else json.dumps(text)


def altium(plan,fullpath,resultpath,marker):
    q=lambda s:literal(s,'pascal'); c=plan['target']
    result=canonical({'plan_hash':digest(plan),'status':'applied_in_memory',
                      'before':plan['expected'],'after':plan['value'],'saved':False})
    # Calls are documented by Altium's PCB API and scripting interface references.
    return f'''// Generated Gantry operation. Run GantryApply once, with exclusive editor access.
// Native save and electrical validation are deliberately not inferred.
Procedure GantryApply;
Var Board : IPCB_Board; Iterator : IPCB_BoardIterator;
    Component, Target : IPCB_Component; Lines : TStringList; Count : Integer;
Begin
  If FileExists({q(marker)}) Then Raise Exception.Create('Gantry operation already started');
  Lines := TStringList.Create;
  Try
    Lines.Add('started'); Lines.SaveToFile({q(marker)});
  Finally Lines.Free; End;
  Board := PCBServer.GetCurrentPCBBoard;
  If Board = Nil Then Raise Exception.Create('No active PCB');
  If Board.IsLibrary Then Raise Exception.Create('PCB libraries are not supported');
  If UpperCase(Board.FileName) <> UpperCase({q(fullpath)}) Then
    Raise Exception.Create('Wrong PCB document');
  Iterator := Board.BoardIterator_Create;
  Target := Nil; Count := 0;
  Try
    Iterator.AddFilter_ObjectSet(MkSet(eComponentObject));
    Iterator.AddFilter_LayerSet(AllLayers);
    Iterator.AddFilter_Method(eProcessAll);
    Component := Iterator.FirstPCBObject;
    While Component <> Nil Do Begin
      If Component.Name.Text = {q(c['selector'])} Then Begin
        Target := Component; Count := Count + 1;
      End;
      Component := Iterator.NextPCBObject;
    End;
  Finally Board.BoardIterator_Destroy(Iterator); End;
  If Count <> 1 Then Raise Exception.Create('Component missing or ambiguous');
  If Target.Comment.Text <> {q(plan['expected'])} Then Raise Exception.Create('Stale comment');
  PCBServer.PreProcess;
  Try
    PCBServer.SendMessageToRobots(Target.Comment.I_ObjectAddress, c_Broadcast, PCBM_BeginModify, c_NoEventData);
    Target.Comment.Text := {q(plan['value'])};
    PCBServer.SendMessageToRobots(Target.Comment.I_ObjectAddress, c_Broadcast, PCBM_EndModify, c_NoEventData);
  Finally PCBServer.PostProcess; End;
  If Target.Comment.Text <> {q(plan['value'])} Then Raise Exception.Create('Readback mismatch');
  Lines := TStringList.Create;
  Try Lines.Add({q(result)}); Lines.SaveToFile({q(resultpath)});
  Finally Lines.Free; End;
End;
'''


def cadence(plan,fullpath,resultpath,marker):
    q=lambda s:literal(s,'skill');c=plan['target']
    result=canonical({'plan_hash':digest(plan),'status':'applied_in_memory',
                      'before':plan['expected'],'after':plan['value'],'saved':False})
    return f'''; Generated Gantry operation. Load, then call gantryApply() once.
; Allegro PCB Editor only. Native save is a separate operator action.
procedure(gantryApply()
  let((design props selected before port mark)
    when(isFile({q(marker)}) error("Gantry operation already started"))
    port=outfile({q(marker)})
    unless(port error("Cannot persist dispatch marker"))
    fprintf(port "started\\n") close(port)
    design=axlDBGetDesign()
    unless(design error("No active Allegro design"))
    unless(equal(axlGetDrawingName() {q(fullpath)}) error("Wrong Allegro document; full path must match"))
    props=axlDBGetProperties(design)
    selected=assoc({q(c['selector'])} props)
    unless(selected error("Existing design property required"))
    before=cadr(selected)
    unless(stringp(before) && equal(before {q(plan['expected'])}) error("Stale or non-string property"))
    mark=axlDBTransactionStart()
    unless(axlDBAddProp(design list({q(c['selector'])} {q(plan['value'])}))
      axlDBTransactionRollback(mark) error("Property update refused"))
    unless(equal(cadr(assoc({q(c['selector'])} axlDBGetProperties(design))) {q(plan['value'])})
      axlDBTransactionRollback(mark) error("Readback mismatch"))
    axlDBTransactionCommit(mark)
    port=outfile({q(resultpath)})
    unless(port error("Result receipt unavailable; do not retry"))
    fprintf(port "%s\\n" {q(result)}) close(port)
  )
)
'''


def prepare_script(root,config,expected,value,reason,refs,destination):
    require(isinstance(config,dict) and set(config)=={'product','document','selector','version'}
            and config['product'] in {'altium','cadence'},'unsupported','Supported native scripting product required')
    require(isinstance(config['selector'],str) and re.fullmatch('[A-Za-z0-9_.-]{1,100}',config['selector']),
            'invalid_input','Bounded component designator or property name required')
    require(isinstance(config['version'],str) and 0<len(config['version'])<=100,'invalid_input','Declared native version required')
    for text in (expected,value,reason):
        require(isinstance(text,str) and len(text)<=2000,'invalid_input','Bounded text required')
        literal(text,'skill')
    require(reason,'invalid_input','Reason required')
    safe_file(config['document']);root=root_path(root)
    suffix='.pcbdoc' if config['product']=='altium' else '.brd'
    require(config['document'].lower().endswith(suffix),'unsupported','Native PCB file required')
    raw=read_file(root,config['document'])
    require((root/config['document']).stat().st_nlink==1,'scope_denied','Hardlinked native file denied')
    plan={'version':1,'intent_id':secrets.token_hex(16),'target':config,'expected':expected,
          'value':value,'reason':reason,'requirement_refs':refs,
          'operator_root':root_identity(root),
          'baseline_file_hash':hashlib.sha256(raw).hexdigest(),
          'baseline_value_source':'operator_supplied_checked_in_native_script'}
    h=digest(plan);dest=Path(destination).absolute();fullpath=str(root/config['document'])
    script_name='operation.pas' if config['product']=='altium' else 'operation.il'
    render=altium if config['product']=='altium' else cadence
    source=render(plan,fullpath,str(dest/'result.json'),str(dest/'started'))
    bundle=make_bundle(config['product'],'native-'+h[:24],
        {'plan.json':canonical(plan).encode(),'before/native/'+config['document']:raw,script_name:source.encode()},refs,
        source={'native_script_plan':h},missing=['Native script not executed','Native version is operator declared',
            'Unsaved editor state not captured at preparation','Full file CAS not available'])
    write_bundle(destination,bundle)
    # Convenience copy outside the immutable payload; collection verifies it too.
    path=dest/script_name
    with path.open('xb') as f:f.write(source.encode())
    path.chmod(0o600)
    return {'plan_hash':h,'script':script_name,'native_write':False,'status':'awaiting_native_host_execution'}


def collect_script(package,root):
    root=root_path(root);package=Path(package);b=read_bundle(package)
    plan=parse_json(b['files']['plan.json']);h=digest(plan)
    require(b['manifest']['source']=={'native_script_plan':h},'integrity_error','Script plan changed')
    require(plan['operator_root']==root_identity(root),'scope_denied','Use the operator root where the script was prepared')
    require(plan['requirement_refs']==b['manifest']['requirement_refs'],'integrity_error','Requirement references differ')
    c=plan['target'];require(c['product'] in {'altium','cadence'},'unsupported','Native scripting product required')
    script='operation.pas' if c['product']=='altium' else 'operation.il'
    render=altium if c['product']=='altium' else cadence
    expected_source=render(plan,str(root/c['document']),str(package.absolute()/'result.json'),str(package.absolute()/'started'))
    require(b['files'][script]==expected_source.encode(),'integrity_error','Script or package location differs from prepared operation')
    require(hashlib.sha256(b['files']['before/native/'+c['document']]).hexdigest()==plan['baseline_file_hash'],
            'integrity_error','Native baseline bytes differ')
    require(read_file(package,script)==b['files'][script],'integrity_error','Executed script copy changed')
    require((package/'started').is_file(),'not_found','No native dispatch marker; script has not reported execution')
    read_file(package,'started')
    files=dict(b['files'])
    if (package/'result.json').exists():
        raw=read_file(package,'result.json');r=parse_json(raw)
        require(r=={'plan_hash':h,'status':'applied_in_memory','before':plan['expected'],'after':plan['value'],'saved':False},
                'integrity_error','Native result does not match script contract')
        files['native-result.json']=raw;status='applied_in_memory'
    else:status='unknown'
    files['after/native/'+c['document']]=read_file(root,c['document'])
    return make_bundle(c['product'],'native-'+h[:24],files,plan['requirement_refs'],
        source={'native_script_plan':h,'outcome':status},missing=['Native save not verified',
            'Script runtime/version not qualified','Physical/electrical verification not performed',
            'Dependencies outside selected file not captured'])
