import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gantry.integrations.bundle import make_bundle, read_bundle, write_bundle
from gantry.model import Fault
from gantry.integrations.kicad import check_kicad
from gantry.integrations.mcap_capture import capture_mcap


def record(op, data):
    return struct.pack('<BQ', op, len(data)) + data


def string(text):
    data = text.encode()
    return struct.pack('<I', len(data)) + data


def recording(index=True):
    magic = b'\x89MCAP0\r\n'
    header = record(1, string('ros2') + string('test recorder'))
    channel = record(4, struct.pack('<HH', 1, 0) + string('/status') + string('cdr') + bytes(4))
    message = record(5, struct.pack('<HIQQ', 1, 0, 123, 123) + bytes(8))
    data = magic + header + channel + message + record(15, bytes(4))
    stats = struct.pack('<QHIIIIQQI', 1, 0, 1, 0, 0, 0, 123, 123, 10) + struct.pack('<HQ', 1, 1)
    summary = channel + record(11, stats) if index else b''
    return data + summary + record(2, struct.pack('<QQI', len(data) if index else 0, 0, 0)) + magic


class RoboticsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.binary = self.root / 'kicad-cli'
        self.binary.touch(mode=0o700)

    def test_mcap_summary_and_lossless_roundtrip(self):
        raw = recording()
        (self.project/'run.mcap').write_bytes(raw)
        bundle = capture_mcap(self.project, 'run.mcap', 'bench', [])
        write_bundle(self.root/'out', bundle)
        loaded = read_bundle(self.root/'out')
        self.assertEqual(loaded['files']['recording/run.mcap'], raw)
        summary = json.loads(loaded['files']['summary.json'])
        self.assertEqual(summary['profile'], 'ros2')
        self.assertEqual(summary['channels'][0]['topic'], '/status')
        self.assertEqual(summary['channels'][0]['message_count'], 1)
        self.assertEqual(summary['statistics']['end_ns'], 123)
        self.assertEqual(loaded['manifest']['verification'], 'unverified')

    def test_mcap_no_index_and_truncation(self):
        path = self.project/'run.mcap'
        path.write_bytes(recording(False))
        bundle = capture_mcap(self.project, path.name, 'bench', [])
        self.assertIsNone(json.loads(bundle['files']['summary.json'])['statistics'])
        self.assertTrue(bundle['manifest']['missing'])
        path.write_bytes(recording()[:-3])
        with self.assertRaises(Fault):
            capture_mcap(self.project, path.name, 'bench', [])

    def test_kicad_checks_copy_and_preserves_findings(self):
        board = self.project/'main.kicad_pcb'
        board.write_bytes(b'initial board')
        (self.project/'main.kicad_pro').write_bytes(b'{}')
        report = {'$schema':'https://schemas.kicad.org/drc.v1.json', 'source':board.name,
                  'kicad_version':'10.0.6','violations':[{}], 'unconnected_items':[], 'schematic_parity':[]}
        def run(binary, argv, scratch):
            self.assertEqual(binary, self.binary)
            self.assertIn('--exit-code-violations', argv)
            self.assertEqual((scratch/'design'/board.name).read_bytes(), board.read_bytes())
            self.assertTrue((scratch/'design/main.kicad_pro').is_file())
            (scratch/'report.json').write_text(json.dumps(report))
            return 5
        with patch('gantry.integrations.kicad._run_check', side_effect=run):
            bundle = check_kicad(self.project, board.name, [], self.binary, 'demo', [])
        self.assertEqual(bundle['files']['design/main.kicad_pcb'], board.read_bytes())
        self.assertEqual(bundle['manifest']['source']['outcome'], 'findings')
        self.assertEqual(bundle['manifest']['source']['counts']['violations'], 1)

    def test_kicad_tool_failure_and_wrong_report_fail_closed(self):
        board = self.project/'main.kicad_pcb'
        board.write_bytes(b'board')
        with patch('gantry.integrations.kicad._run_check', return_value=3), self.assertRaises(Fault):
            check_kicad(self.project, board.name, [], self.binary, 'demo', [])
        def wrong(binary, argv, scratch):
            (scratch/'report.json').write_text('{"source":"other.kicad_pcb"}')
            return 0
        with patch('gantry.integrations.kicad._run_check', side_effect=wrong), self.assertRaises(Fault):
            check_kicad(self.project, board.name, [], self.binary, 'demo', [])

    def test_freecad_missing_host_fails_without_publication(self):
        from gantry.integrations.freecad_step import capture_step
        (self.project/'board.step').write_bytes(b'ISO-10303-21;')
        with self.assertRaises(Fault) as ctx:
            capture_step(self.project, 'board.step', self.root/'FreeCAD.app', 'geometry', [])
        self.assertEqual(ctx.exception.code, 'tool_unavailable')

    def test_onnx_reads_interface_without_following_external_weight_paths(self):
        try:
            import onnx
        except ImportError:
            self.skipTest('optional ONNX dependency')
        from gantry.integrations.onnx_capture import capture_onnx
        from onnx import helper, TensorProto
        value = helper.make_tensor_value_info('samples', TensorProto.FLOAT, ['batch', 3])
        weight = TensorProto(name='unused', data_type=TensorProto.FLOAT, dims=[1], data_location=TensorProto.EXTERNAL)
        weight.external_data.add(key='location', value='does-not-exist.bin')
        graph = helper.make_graph([], 'test', [value], [value], [weight])
        (self.project/'model.onnx').write_bytes(helper.make_model(graph).SerializeToString())
        bundle = capture_onnx(self.project, 'model.onnx', 'model', [])
        view = json.loads(bundle['files']['interface.json'])
        self.assertEqual(view['inputs'][0]['shape'], ['batch',3])
        self.assertEqual(bundle['manifest']['verification'], 'unverified')
        self.assertEqual(set(bundle['files']), {'model/model.onnx','interface.json'})

    def test_windows_preflight_distinguishes_sdk_and_missing_host(self):
        from gantry.native.preflight import inspect_host
        with patch('gantry.native.preflight.platform.system', return_value='Darwin'):
            result = inspect_host()
        rows = {r['id']:r for r in result['products']}
        self.assertEqual(rows['solidworks']['status'], 'windows_host_required')
        self.assertEqual(rows['zuken-e3']['status'], 'blocked_sdk')
        self.assertFalse(any(r['runtime_verified'] for r in rows.values()))

    def test_corrupted_index_checksum_and_overlong_frame_are_rejected(self):
        data = bytearray(recording())
        data[-12:-8] = struct.pack('<I', 1)
        path = self.project/'bad.mcap'
        path.write_bytes(data)
        with self.assertRaises(Fault):
            capture_mcap(self.project, path.name, 'run', [])
        data = bytearray(recording())
        data[9:17] = bytes([255])*8
        path.write_bytes(data)
        with self.assertRaises(Fault):
            capture_mcap(self.project, path.name, 'run', [])
