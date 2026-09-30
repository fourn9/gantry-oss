"""Synthetic HTTP capture/share/restore demo; no inference or physical validation."""
import base64
import json
from pathlib import Path
import tempfile
import threading

from gantry.client import Client
from gantry.continuity_adapter import restore_development_state
from gantry.server import Server
from gantry.service import Service


def main():
    with tempfile.TemporaryDirectory(prefix='gantry-example-') as directory:
        root = Path(directory)
        service = Service(root / 'ledger')
        token = service.bootstrap()['token']
        server = Server(('127.0.0.1', 0), service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = Client('http://127.0.0.1:' + str(server.server_port), token)
        def artifact(files):
            return client.call('capture_artifact', {'files': {
                name: base64.b64encode(text.encode()).decode() for name, text in files.items()
            }})['revision_id']
        try:
            baseline = artifact({'gripper.json': '{"opening_mm":40}', 'control.py': 'opening_mm = 40\n'})
            session = client.call('connect_development', {
                'title': 'Gripper development', 'snapshot': baseline,
                'capture': {'scope': 'saved files', 'missing': ['earlier history']},
                'unverified': ['physical performance'], 'mode': 'record', 'actors': ['admin'],
                'write_scope': ['gripper.json', 'control.py'], 'recipes': {},
                'max_executions': 0, 'timeout_seconds': 30, 'max_parallel': 1})
            state = client.call('initialize_continuity', {
                'session_id': session['id'], 'version': session['version'],
                'summary': 'Imported current gripper and controller',
                'hierarchy': [{'id': 'gripper', 'title': 'Gripper', 'kind': 'subsystem',
                               'paths': ['gripper.json', 'control.py'], 'editable': True}],
                'context': {'requirements': ['Grasp a wider test object'],
                            'constraints': ['No hardware operation'], 'decisions': [],
                            'open_questions': ['Check available actuator travel'], 'environment': {}}})
            change = client.call('begin_change', {
                'state_id': state['id'], 'title': 'Wider opening', 'purpose': 'Explore additional travel',
                'write_scope': ['gripper.json', 'control.py'], 'dependencies': [], 'assignee': 'admin'})
            candidate = artifact({'gripper.json': '{"opening_mm":45}', 'control.py': 'opening_mm = 45\n'})
            checkpoint = client.call('checkpoint_change', {
                'change_id': change['id'], 'version': change['version'], 'snapshot': candidate,
                'summary': 'Design and control candidate saved', 'rationale': 'Test a wider opening',
                'unfinished': ['Actuator travel and collision checks'], 'work_status': 'paused',
                'capture': {'scope': 'saved files', 'missing': ['unsaved edits']}})
            client.call('share_change', {'change_id': change['id'], 'version': checkpoint['change']['version']})
            view = client.call('get_development_state', {'state_id': checkpoint['state']['id']})
            restored = restore_development_state(client, checkpoint['state']['id'], root/'handoff', 'demo-restore')
            assert (Path(restored['workspace'])/'control.py').read_text() == 'opening_mm = 45\n'
            assert view['status']['verification'] == 'unverified'
            assert view['status']['adoption'] == 'unadopted'
            assert client.call('verify')['valid']
            assert client.call('replay')['matched']
            print(json.dumps({'status': view['status'], 'restored_bytes_match': True,
                              'event_log_verified': True, 'replay_matched': True,
                              'model_calls': 0}, indent=2))
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    main()
