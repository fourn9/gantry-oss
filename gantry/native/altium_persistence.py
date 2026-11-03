"""Opt-in host script; native execution still requires Altium qualification."""
from pathlib import Path
from ..model import canonical, digest


def render(plan, fullpath, resultpath, marker):
    from .scripts import literal
    q = lambda text: literal(text, 'pascal')
    package = Path(resultpath).parent
    baseline = str(package / 'payload' / 'before' / 'native' / plan['target']['document'])
    snapshot = str(package / 'native-saved.PcbDoc')
    receipt = canonical(dict(plan_hash=digest(plan), status='saved_and_reloaded',
        before=plan['expected'], after=plan['value'], saved=True, reloaded=True,
        capture='native-saved.PcbDoc'))
    # Source: https://www.altium.com/documentation/altium-dxp-developer/iserverdocument-interface
    # Source: https://www.altium.com/documentation/altium-dxp-developer/iclient-interface
    return f'''// Generated Gantry v2 operation. Exclusive editor access is required.
// Host-reported persistence is not electrical/physical verification.
Function GantrySameFile(A, B : String) : Boolean;
Var Left, Right : TFileStream; X, Y : Integer; TailX, TailY : Byte;
Begin
  Result := False;
  Left := TFileStream.Create(A, fmOpenRead or fmShareDenyWrite);
  Try
    Right := TFileStream.Create(B, fmOpenRead or fmShareDenyWrite);
    Try
      If Left.Size <> Right.Size Then Exit;
      While Left.Size - Left.Position >= 4 Do Begin
        Left.ReadBuffer(X, 4); Right.ReadBuffer(Y, 4);
        If X <> Y Then Exit;
      End;
      While Left.Position < Left.Size Do Begin
        Left.ReadBuffer(TailX, 1); Right.ReadBuffer(TailY, 1);
        If TailX <> TailY Then Exit;
      End;
      Result := True;
    Finally Right.Free; End;
  Finally Left.Free; End;
End;

Function GantryFindComponent(Board : IPCB_Board) : IPCB_Component;
Var Iterator : IPCB_BoardIterator; Component : IPCB_Component; Count : Integer;
Begin
  Result := Nil; Count := 0;
  Iterator := Board.BoardIterator_Create;
  Try
    Iterator.AddFilter_ObjectSet(MkSet(eComponentObject));
    Iterator.AddFilter_LayerSet(AllLayers);
    Iterator.AddFilter_Method(eProcessAll);
    Component := Iterator.FirstPCBObject;
    While Component <> Nil Do Begin
      If Component.Name.Text = {q(plan['target']['selector'])} Then Begin
        Result := Component; Count := Count + 1;
      End;
      Component := Iterator.NextPCBObject;
    End;
  Finally Board.BoardIterator_Destroy(Iterator); End;
  If Count <> 1 Then Raise Exception.Create('Component missing or ambiguous');
End;

Procedure GantryApply;
Var Board : IPCB_Board; Target : IPCB_Component; Document : IServerDocument;
    Lines : TStringList; InputFile, OutputFile : TFileStream;
Begin
  If FileExists({q(marker)}) Then Raise Exception.Create('Gantry operation already started');
  If FileExists({q(snapshot)}) Or FileExists({q(resultpath)}) Then
    Raise Exception.Create('Existing outcome; do not overwrite');
  Lines := TStringList.Create;
  Try Lines.Add('started'); Lines.SaveToFile({q(marker)});
  Finally Lines.Free; End;
  If Client = Nil Then Raise Exception.Create('Client unavailable');
  Document := Client.GetDocumentByPath({q(fullpath)});
  If Document = Nil Then Raise Exception.Create('Document not open');
  If Document.Modified Then Raise Exception.Create('Unsaved editor changes');
  If Not GantrySameFile({q(fullpath)}, {q(baseline)}) Then
    Raise Exception.Create('Native file changed since preparation');
  Board := PCBServer.GetCurrentPCBBoard;
  If Board = Nil Then Raise Exception.Create('No active PCB');
  If Board.IsLibrary Then Raise Exception.Create('PCB libraries are not supported');
  If UpperCase(Board.FileName) <> UpperCase({q(fullpath)}) Then Raise Exception.Create('Wrong PCB');
  Target := GantryFindComponent(Board);
  If Target.Comment.Text <> {q(plan['expected'])} Then Raise Exception.Create('Stale comment');
  PCBServer.PreProcess;
  Try
    PCBServer.SendMessageToRobots(Target.Comment.I_ObjectAddress, c_Broadcast, PCBM_BeginModify, c_NoEventData);
    Target.Comment.Text := {q(plan['value'])};
    PCBServer.SendMessageToRobots(Target.Comment.I_ObjectAddress, c_Broadcast, PCBM_EndModify, c_NoEventData);
  Finally PCBServer.PostProcess; End;
  Document.Modified := True;
  If Not Document.DoFileSave({q(plan['save_format'])}) Then Raise Exception.Create('Save failed');
  If Document.Modified Then Raise Exception.Create('Document still dirty after save');
  If Not Document.DoFileLoad Then Raise Exception.Create('Reload failed');
  If Document.Modified Then Raise Exception.Create('Reloaded document is dirty');
  Board := PCBServer.GetCurrentPCBBoard;
  If Board = Nil Then Raise Exception.Create('Reloaded PCB unavailable');
  If UpperCase(Board.FileName) <> UpperCase({q(fullpath)}) Then Raise Exception.Create('Wrong reloaded PCB');
  Target := GantryFindComponent(Board);
  If Target.Comment.Text <> {q(plan['value'])} Then Raise Exception.Create('Reloaded value mismatch');
  InputFile := TFileStream.Create({q(fullpath)}, fmOpenRead or fmShareDenyWrite);
  Try
    OutputFile := TFileStream.Create({q(snapshot)}, fmCreate);
    Try OutputFile.CopyFrom(InputFile, 0); Finally OutputFile.Free; End;
  Finally InputFile.Free; End;
  Lines := TStringList.Create;
  Try Lines.Add({q(receipt)}); Lines.SaveToFile({q(resultpath)});
  Finally Lines.Free; End;
End;
'''
