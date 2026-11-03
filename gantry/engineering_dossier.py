"""Loss-explicit engineering questions for Mentor, not generated design answers."""


def dossier(state_id, baseline_id, engineering, diffs, requirement_coverage):
    rows=[]
    for check in engineering.get('checks', [])[:100]:
        result=check.get('physical_result', {})
        dependent=check.get('dependency_stale', [])
        rows.append({'id':check['id'],'scope':check['scope'],'components':check['components'],
            'required':check['required'],'recorded_status':check['status'],
            'applicable_status':check['effective_status'],'inputs':check['inputs'],
            'evidence':check.get('evidence', {}),'requirement_refs':check.get('requirement_refs', []),
            'acceptance_and_observations':result.get('comparisons', []),
            'execution_or_binding_problems':result.get('reasons', []),
            'dependency_stale':dependent,'stale_inputs':check.get('stale_inputs', []),
            'stale_evidence':check.get('stale_evidence', []),
            'limitations':result.get('limitations', []),
            'action':'reassess_dependency_then_validate' if dependent else
                     'provide_bound_evidence' if check['effective_status'] in {'unknown','unverified'} else
                     'propose_correction_and_retest' if check['effective_status']=='fail' else 'review_scope_and_limitations'})
    return {'version':1,'input_state':state_id,'baseline_state':baseline_id,
        'components':engineering.get('components', [])[:100],
        'component_count':len(engineering.get('components', [])),
        'components_truncated':len(engineering.get('components', []))>100,
        'dependency_impact':engineering.get('dependency_impact', {'coverage':'not declared'}),
        'changed_files':[{k:d[k] for k in ('path','before','after') if k in d} for d in diffs],
        'checks':rows,'checks_truncated':len(engineering.get('checks', []))>100,
        'requirement_coverage':requirement_coverage,'review_gaps':engineering.get('review_gaps', []),
        'review_contract':['Distinguish declared native IDs from independently observed correspondence.',
            'For a proposed correction, cite pinned state and file/evidence; name edit targets and a completion test.',
            'Compare alternatives when proposing CAD versus control changes. Do not invent missing loads or material properties.',
            'Do not substitute partial checks for whole-system acceptance. Missing inputs require investigation, not a pass.',
            'Only the reviewing agent chooses a design recommendation; this dossier merely summarizes recorded evidence.']}
