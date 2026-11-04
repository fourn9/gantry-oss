"""Only worker instances opened by this customer host may be stopped by it."""
import threading

from .bot_worker import BotWorker, configured_client
from .model import Fault, digest, require
from .project_connect import load, private_dir, save
from .crew_setup_client import _private_file


class HostWorkers:
    def __init__(self, journal, *, client_factory=configured_client, infer_fn=None, interval=5):
        self.root = private_dir(journal)
        self.client_factory, self.infer_fn, self.interval = client_factory, infer_fn, interval
        self.workers = {}; self.lock = threading.RLock()

    def start_setup(self, setup_id, prepared):
        with self.lock:
            added = []
            try:
                for runtime in prepared['runtimes']:
                    config = load(_private_file(runtime['config_file'])); bot_id = config['bot_id']
                    handle = self.workers.get(bot_id)
                    if handle and not handle['thread'].is_alive():
                        del self.workers[bot_id]; handle = None
                    if handle:
                        require(not handle['done'].is_set() and not handle['worker'].lost.is_set() and
                                digest(config) == handle['config_hash'],
                                'runtime_unavailable', 'Prior worker must finish stopping before it can restart')
                        if setup_id not in handle['setups']:
                            handle['setups'].add(setup_id); added.append(bot_id)
                        continue
                    worker = BotWorker(self.client_factory(config), config, self.root, self.infer_fn)
                    worker.__enter__()
                    handle = {'worker': worker, 'config_hash': digest(config), 'setups': {setup_id},
                              'done': threading.Event(), 'ready': threading.Event()}
                    self.workers[bot_id] = handle; added.append(bot_id)
                    thread = threading.Thread(target=self._run, args=(handle,), daemon=True)
                    handle['thread'] = thread; thread.start()
                return added
            except BaseException:
                self.stop_setup(setup_id, only=added)
                raise

    def run_setup(self, setup_id):
        with self.lock:
            for handle in self.workers.values():
                if setup_id in handle['setups']: handle['ready'].set()

    def _run(self, handle):
        worker = handle['worker']
        try:
            while not handle['ready'].wait(.1):
                if handle['done'].is_set(): return
            while not handle['done'].is_set() and not worker.lost.is_set():
                worker.tick()
                if handle['done'].wait(self.interval): break
        except Exception as exc:
            save(worker.root/'host-worker-error.json', {'type': type(exc).__name__, 'message': str(exc)})
        finally:
            handle['done'].set()
            worker.__exit__(None, None, None)

    def _stop(self, handle):
        handle['done'].set()
        worker = handle['worker']; worker.lost.set(); worker.stop.set()
        # Fence immediately, even if the provider is still returning. The thread
        # retains its file lock until that invocation exits and cannot submit work.
        try:
            worker.client.call('stop_bot_runtime', {'bot_id': worker.bot_id, 'fence': worker.runtime['fence']},
                'setup-worker-stop:'+digest([worker.bot_id, worker.runtime['fence']]))
        except Fault as exc:
            if exc.code != 'stale_basis': raise
            current = worker.client.call('get_persistent_bot', {'bot_id': worker.bot_id})['runtime']
            require(not current or current['presence'] == 'offline' or
                    current.get('instance_id') != worker.runtime['instance_id'],
                    'runtime_unavailable', 'Owned worker shutdown has not been confirmed')
        finally: handle['thread'].join(timeout=1)

    def stop_setup(self, setup_id, only=None):
        """Explicit Stop fences shared runtimes; rollback detaches only new references."""
        with self.lock:
            error = None
            for bot_id, handle in list(self.workers.items()):
                if setup_id not in handle['setups'] or (only is not None and bot_id not in only): continue
                if only is not None and handle['setups'] != {setup_id}:
                    handle['setups'].discard(setup_id); continue
                try:
                    self._stop(handle)
                    handle['setups'].clear()
                    if not handle['thread'].is_alive(): del self.workers[bot_id]
                except Exception as exc: error = exc
            if error: raise error

    def stop_all(self):
        with self.lock:
            for handle in list(self.workers.values()):
                try: self._stop(handle)
                except Exception: pass  # Disconnect cleanup also relies on Core's finite runtime lease.
            self.workers = {bid: h for bid, h in self.workers.items() if h['thread'].is_alive()}
