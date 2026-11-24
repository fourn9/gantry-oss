"""Inspect the declared interface of one serialized model without executing it."""
import hashlib
from pathlib import Path

from ..model import canonical, Fault, require
from .bundle import make_bundle, read_file


def capture_onnx(root, path, source_id, refs):
    require(Path(path).suffix.lower() == '.onnx', 'invalid_input', 'Select an ONNX protobuf model')
    raw = read_file(root, path)
    try:
        from onnx import ModelProto, TensorProto
        from google.protobuf.message import DecodeError
    except ImportError:
        raise Fault('tool_unavailable', 'Install gantry-ledger[onnx] to inspect model interfaces') from None
    model = ModelProto()
    try:
        model.ParseFromString(raw)
    except DecodeError:
        raise Fault('invalid_input', 'Malformed ONNX protobuf') from None
    require(model.ir_version > 0 and model.HasField('graph'), 'invalid_input', 'ONNX graph required')
    graph = model.graph
    require(len(graph.input)+len(graph.output) <= 512 and len(model.opset_import) <= 128,
            'acquisition_limit', 'Model interface exceeds index limit')

    def port(value):
        kind = value.type.WhichOneof('value')
        result = {'name': value.name, 'kind': kind}
        if kind == 'tensor_type':
            tensor = value.type.tensor_type
            require(len(tensor.shape.dim) <= 64, 'acquisition_limit', 'Tensor rank exceeds index limit')
            result['element_type'] = TensorProto.DataType.Name(tensor.elem_type)
            result['shape'] = ([getattr(d, d.WhichOneof('value')) if d.WhichOneof('value') else None
                                for d in tensor.shape.dim] if tensor.HasField('shape') else None)
        return result

    view = {'ir_version':model.ir_version,'graph':graph.name,'node_count':len(graph.node),
            'opsets':[{'domain':op.domain,'version':op.version} for op in model.opset_import],
            'inputs':[port(v) for v in graph.input], 'outputs':[port(v) for v in graph.output]}
    return make_bundle('onnx', source_id, {'model/'+path:raw, 'interface.json':canonical(view).encode()}, refs,
                       {'interface.json':['/inputs','/outputs']}, source={'kind':'saved_onnx_interface','model':path},
                       source_revision=hashlib.sha256(raw).hexdigest(),
                       missing=['separately stored weights or custom operators', 'inference evaluation', 'training history'])
