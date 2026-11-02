"""Find the unfinished inference without resetting completed Bot effects."""
import json


def pending_inference(directory, journal, config):
    if journal['phase'] != 'inference': return None
    plan = directory/'learning'/'plan.json'
    if config.get('experience_learning') and plan.exists():
        saved = json.loads(plan.read_text())
        if 'receipt' not in saved and 'result' not in saved and not (directory/'learning'/'inference'/'receipt.json').exists():
            return directory/'learning'/'inference'/'model'
    if config.get('agent_loop'):
        loop = directory/'actions'/'loop.json'
        state = json.loads(loop.read_text()) if loop.exists() else {'next': 0}
        step = directory/'actions'/str(state['next'])
        if (step/'action.json').exists(): return None
        return step/'model'
    return directory/'model'
