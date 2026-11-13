"""Small OCCT geometry boundary, without VTK or executable CAD recipes.

Uses official cadquery-ocp-novtk bindings. STEPControl Reader/Writer and
BRepAlgoAPI contracts: https://dev.opencascade.org/doc/refman/html/index.html
The installed 7.9 binding docstrings and analytic regression tests qualify the API.
"""
from importlib.metadata import PackageNotFoundError, version
from types import SimpleNamespace


def runtime():
    try:
        current = version('cadquery-ocp-novtk')
    except PackageNotFoundError:
        raise ImportError('Install Gantry [cad] in a fresh environment (OCP no-VTK required)') from None
    try:
        version('cadquery-ocp')
    except PackageNotFoundError:
        return 'OCP no-VTK ' + current
    raise ImportError('Conflicting OCP distributions: recreate the CAD environment; do not mix cadquery-ocp and cadquery-ocp-novtk')


BACKEND = runtime()
from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.StlAPI import StlAPI_Reader
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape, TopTools_ListOfShape
from OCP.TopoDS import TopoDS_Compound, TopoDS_Shape
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec


class Shape:
    def __init__(self, wrapped):
        if wrapped.IsNull():
            raise ValueError('CAD operation returned a null shape')
        self.wrapped = wrapped

    def isValid(self):
        return BRepCheck_Analyzer(self.wrapped).IsValid()

    def _parts(self, kind):
        parts = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(self.wrapped, kind, parts)
        return [Shape(parts.FindKey(i)) for i in range(1, parts.Extent()+1)]

    def Solids(self):
        return self._parts(TopAbs_SOLID)

    def Faces(self):
        return self._parts(TopAbs_FACE)

    def Volume(self):
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(self.wrapped, props)
        return props.Mass()

    def BoundingBox(self):
        bounds = Bnd_Box()
        BRepBndLib.AddOptimal_s(self.wrapped, bounds, False, False)
        if bounds.IsVoid() or bounds.IsOpen():
            raise ValueError('CAD bounds are void or unbounded')
        return SimpleNamespace(**dict(zip(('xmin','ymin','zmin','xmax','ymax','zmax'), bounds.Get())))

    def translate(self, vector):
        transform = gp_Trsf(); transform.SetTranslation(gp_Vec(*vector))
        return Shape(BRepBuilderAPI_Transform(self.wrapped, transform, True).Shape())

    def _boolean(self, other, operation):
        # Two-shape constructors build immediately; configure non-destructive mode first.
        arguments = TopTools_ListOfShape(); arguments.Append(self.wrapped)
        tools = TopTools_ListOfShape(); tools.Append(other.wrapped)
        result = operation()
        result.SetArguments(arguments); result.SetTools(tools)
        result.SetNonDestructive(True); result.Build()
        if not result.IsDone():
            raise ValueError('CAD boolean operation failed')
        return Shape(result.Shape())

    def cut(self, other):
        return self._boolean(other, BRepAlgoAPI_Cut)

    def fuse(self, other):
        return self._boolean(other, BRepAlgoAPI_Fuse)

    def intersect(self, other):
        return self._boolean(other, BRepAlgoAPI_Common)

    def distance(self, other):
        result = BRepExtrema_DistShapeShape(self.wrapped, other.wrapped)
        if not result.IsDone() or not result.NbSolution():
            raise ValueError('CAD distance calculation failed')
        return result.Value()


def box(x, y, z):
    return Shape(BRepPrimAPI_MakeBox(gp_Pnt(-x/2, -y/2, -z/2), x, y, z).Shape())


def cylinder(radius, height):
    return Shape(BRepPrimAPI_MakeCylinder(radius, height).Shape())


def compound(shapes):
    result = TopoDS_Compound(); builder = BRep_Builder(); builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result, shape.wrapped)
    return Shape(result)


def import_step(path):
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone or not reader.TransferRoots():
        raise ValueError('STEP import failed')
    return Shape(reader.OneShape())


def import_stl(path):
    shape = TopoDS_Shape()
    if not StlAPI_Reader().Read(shape, str(path)):
        raise ValueError('STL import failed')
    return Shape(shape)


def export_step(shape, path):
    writer = STEPControl_Writer()
    if (writer.Transfer(shape.wrapped, STEPControl_AsIs) != IFSelect_RetDone
            or writer.Write(str(path)) != IFSelect_RetDone):
        raise ValueError('STEP export failed')


def export_stl(shape, path):
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    mesh = BRepMesh_IncrementalMesh(shape.wrapped, 0.1, False, 0.1)
    if not mesh.IsDone() or not StlAPI_Writer().Write(shape.wrapped, str(path)):
        raise ValueError('STL export failed')
