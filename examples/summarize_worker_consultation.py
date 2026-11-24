"""Export anonymous metrics and check pairing/budgets from the frozen local model trials."""
import argparse
import csv
import json
import sys
from pathlib import Path


def metrics(model, directory):
    manifest = json.loads((directory/'manifest.json').read_text())
    runs = [json.loads(line) for line in (directory/'runs.jsonl').read_text().splitlines()]
    if len(runs) != len(manifest['groups']) or len(runs) != 48:
        raise ValueError('Cohort is incomplete')
    handoff = manifest.get('study') in ('regression','held-out','transfer')
    pairs = {}
    for row, (case, memory, rotation, routed) in zip(runs, manifest['groups']):
        if (row['case'],row['memory'],row['rotation'],row['routed']) != (case[0], memory, rotation, routed):
            raise ValueError('Run differs from the frozen trial order')
        requester = len(row['decisions']['designer']) + row['wait_reports'] + row.get('auto_submits',0) + row.get('auto_checks',0)
        if handoff and requester != row['recorded_operations']:
            raise ValueError('Model choices, waits and conditional submissions must reconcile with durable operations')
        peer = len(row['decisions']['control'])
        if requester > 8 or peer > 4:
            raise ValueError('Operation budget exceeded')
        key = (row['case'],memory,rotation)
        arms = pairs.setdefault(key,{})
        if routed in arms or row['base_state'] != manifest['states'][row['case']]:
            raise ValueError('Duplicate arm or incorrect starting state')
        arms[routed] = row['base_state']
        accepted = (row['status']=='completed' and row['correct_file'] and bool(row['check_receipts'])
                    and (row['condition']=='consistent' or row['peer_chain']))
        if accepted != row['passed']:
            raise ValueError('Score mismatch')
        extras = {}
        arm = 'routed' if routed else 'prior'
        if handoff:
            arm = 'bound' if routed else 'routed'
            extras = {'cohort':manifest['study'], 'frozen_commit':manifest['commit'], 'conditional_checks':row.get('auto_checks',0), 'wrong_peer_reports':row['wrong_peer_reports'],
                      'wrong_edits':row['wrong_edits'], 'conditional_submits':row['auto_submits']}
        yield {**extras, 'model':model,'case':row['case'],'condition':row['condition'],'memory':int(memory),'rotation':rotation,
               'arm':arm,'status':row['status'],'accepted':int(accepted),
               'correct_file':int(row['correct_file']),'final_state_check':int(bool(row['check_receipts'])),
               'questions':row['questions'],'peer_chain':int(row['peer_chain']),
               'peer_read_source':int(any(q['peer_checked_source'] for q in row['consultations'])),
               'read_correct_report':int(any(q['read_exact_report'] for q in row['consultations'])),
               'cited_answer':int(any(q['cited'] and q['status']=='resolved' for q in row['consultations'])),
               'requester_operations':requester,'peer_operations':peer,'wait_reports':row['wait_reports'],
               'model_calls':row['model_calls'],'seconds':round(row['seconds'],4),'interventions':row['parent_interventions']}
    if len(pairs) != 24 or any(set(arms) != {False,True} for arms in pairs.values()):
        raise ValueError('Missing trial pair')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('qwen',type=Path)
    parser.add_argument('llama',type=Path)
    args = parser.parse_args()
    rows = [*metrics('Qwen2.5-1.5B',args.qwen),*metrics('Llama-3.2-1B',args.llama)]
    writer = csv.DictWriter(sys.stdout,fieldnames=rows[0],lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
