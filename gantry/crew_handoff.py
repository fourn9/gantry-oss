"""A small navigation index over existing version-bound development records."""
from .model import canonical, digest


def handoff_index(source):
    assessment=source.get('design_assessment', {})
    def page(rows, pointer, budget=2000, original=None):
        items=[]; used=0
        for row in rows[:20]:
            size=len(canonical(row).encode())+1
            if used+size > budget: break
            items.append(row); used+=size
        return {'items':items,'total':len(rows),'omitted':len(rows)-len(items),
            'sha256':digest(rows if original is None else original),'pointer':pointer,'source':'full_context'}
    children=[]
    for index, child in enumerate(source.get('children', [])):
        reports=child.get('reports', [])
        children.append({k:child.get(k) for k in ('id','status','output_state')} | {
            'report_sha256':digest(reports[-1]) if reports else None,
            'reports_pointer':f'/children/{index}/reports'})
    return {'baseline_state_id':source['task']['state_id'],
        'current_state_id':source['development']['state']['id'],
        'changes':page(assessment.get('changes', []), '/design_assessment/changes'),
        'open_checks':page(assessment.get('open_checks', []), '/design_assessment/open_checks'),
        'gaps':page(assessment.get('gaps', []), '/design_assessment/gaps'),
        'children':page(children,'/children',original=source.get('children', [])),
        'assessment_partial':assessment.get('partial',False),
        'formal_adoption':False,
        'meaning':'Navigation only, not new evidence or permission. Read referenced reports before relying on omitted details. '
                  'Completed child work does not mean verified or adopted. Recheck current versions at execution.'}
