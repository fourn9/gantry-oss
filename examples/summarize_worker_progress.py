"""Export only anonymous benchmark metrics from the four local Worker study directories."""
import argparse
import csv
import json
import sys
from pathlib import Path


def observations(root, guides=False):
    cohorts = [('focus',''),('retry','-retry')] if guides else [('ordinary',''),('prepared','-prepared')]
    for model in ('qwen', 'llama'):
        for cohort, suffix in cohorts:
            folder = root/(model+suffix)
            manifest = json.loads((folder/'manifest.json').read_text())
            rows = [json.loads(line) for line in (folder/'runs.jsonl').read_text().splitlines()]
            if len(rows) != len(manifest['groups']) or len(rows) != 24:
                raise ValueError(f'{folder.name}: incomplete cohort')
            for idx, (row, group) in enumerate(zip(rows, manifest['groups'])):
                case, memory, feedback, rotation = group[:4]
                extra = {}
                if guides:
                    if row['guided'] != group[4]:
                        raise ValueError(f'{folder.name}: guide mismatch at {idx}')
                    extra = {'guided':int(row['guided']),'model_calls':row['model_calls'],
                             'expected_consultation':int('disagree' in case[1])}
                if [case[0],memory,feedback,rotation] != [row[k] for k in ('case','memory','feedback','rotation')]:
                    raise ValueError(f'{folder.name}: group mismatch at {idx}')
                designer, peer = (row['decisions'][name] for name in ('designer','control'))
                prefix = len(row.get('fixture_prefix', []))
                seen_register_states = set()
                repeated_reads = 0
                for i, action in enumerate(designer):
                    if action['choice'].startswith('Look up'):
                        repeated_reads += int(i >= prefix and action['input_state'] in seen_register_states)
                        seen_register_states.add(action['input_state'])
                choices = [a['choice'] for a in designer[prefix:]]
                model_edits = [c for c in choices if c.startswith('Save ')]
                model_seconds = sum(a['decision_seconds'] for a in designer[prefix:]+peer)
                yield {'model':model,'cohort':cohort,'case':case[0],'lesson':int(memory),'edit_feedback':int(feedback),
                       'rotation':rotation,'order':idx,**extra,'frozen_commit':manifest['commit'],'passed':int(row['passed']),
                       'status':row['status'],'correct_file':int(row['correct_file']),'exact_pass_receipts':len(row['check_receipts']),
                       'fixture_choices':prefix,'designer_choices':len(choices),'peer_choices':len(peer),'model_edits':len(model_edits),
                       'model_reads_register':sum(c.startswith('Look up') for c in choices),
                       'repeat_register_same_state':repeated_reads,
                       'model_duplicate_saves':row['duplicate_saves'] - int(prefix==3),
                       'checks':row['checks'],'peer_tasks_run':int(bool(peer)),
                       'peer_reads_correct_source':int(any(c['peer_checked_source'] for c in row['consultations'])),
                       'requester_reads_correct_report':int(any(c['read_exact_report'] for c in row['consultations'])),
                       'resolutions_with_citation':sum(c['cited'] and c['status']=='resolved' for c in row['consultations']),
                       'seconds':round(row['seconds'],4),'model_seconds':round(model_seconds,4),
                       'parent_interventions':row['parent_interventions']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--guides',action='store_true',help='Export the paired evidence-guide experiments')
    args = parser.parse_args()
    rows = list(observations(args.root,args.guides))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
