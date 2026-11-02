"""Compare external measurements with frozen criteria, never certify physics."""
import math
from .model import require


def finite(value):
    return type(value) in (float,int) and math.isfinite(value)


def evaluate(check, report, hashes):
    criteria=check.get('criteria')
    require(isinstance(criteria,list) and 1<=len(criteria)<=100,'invalid_input','Nonempty bounded criteria required')
    seen=set()
    for c in criteria:
        require(isinstance(c,dict) and set(c)<={'metric','unit','min','max'}
                and isinstance(c.get('metric'),str) and c['metric'] and c['metric'] not in seen
                and isinstance(c.get('unit'),str) and c['unit'] and ('min' in c or 'max' in c)
                and all(finite(c[k]) for k in ('min','max') if k in c)
                and (not {'min','max'}<=set(c) or c['min']<=c['max']),
                'invalid_input','Distinct metrics with finite ordered limits and units required')
        seen.add(c['metric'])
    require(isinstance(check.get('inputs'),list) and check['inputs'] and all(isinstance(p,str) for p in check['inputs']) and set(check['inputs'])<=set(hashes),
            'invalid_input','Check inputs must exist in candidate')
    for key in ('conditions','evaluator','environment'):
        require(isinstance(check.get(key),dict) and check[key],'invalid_input','Explicit '+key+' required')
    require(set(check['evaluator'])=={'name','version'} and all(isinstance(v,str) and v for v in check['evaluator'].values()),
            'invalid_input','Evaluator name and version required')
    expected={p:hashes[p] for p in check['inputs']}
    reasons=[]; rows=[]
    if not isinstance(report,dict): reasons.append('report_missing_or_invalid'); report={}
    if check.get('requirement_refs') and report.get('requirement_refs') != check['requirement_refs']:
        reasons.append('requirement_refs_mismatch')
    if report.get('status')!='completed':reasons.append('execution_not_completed')
    for key,value in [('inputs',expected),('conditions',check['conditions']),('evaluator',check['evaluator']),('environment',check['environment'])]:
        if report.get(key)!=value:reasons.append(key+'_mismatch')
    if not isinstance(report.get('limitations'),list) or not all(isinstance(v,str) for v in report.get('limitations',[])):
        reasons.append('limitations_not_declared')
    measurements=report.get('measurements',{})
    for c in criteria:
        m=measurements.get(c['metric']) if isinstance(measurements,dict) else None
        valid=isinstance(m,dict) and finite(m.get('value')) and m.get('unit')==c['unit']
        passed=valid and ('min' not in c or m['value']>=c['min']) and ('max' not in c or m['value']<=c['max'])
        if not valid:reasons.append('missing_or_invalid_measurement:'+c['metric'])
        rows.append({'criterion':c,'observation':m if valid else None,'status':'pass' if passed else 'fail' if valid else 'unknown'})
    status='unknown' if reasons else 'fail' if any(r['status']=='fail' for r in rows) else 'pass'
    return {'status':status,'reasons':reasons,'comparisons':rows,'inputs':expected,
            'conditions':check['conditions'],'evaluator':check['evaluator'],'environment':check['environment'],
            'limitations':report.get('limitations',[]),
            'provenance':'Submitted external measurements; thresholds checked, physical model not certified'}
