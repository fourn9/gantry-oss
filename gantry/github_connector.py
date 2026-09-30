"""Read-only GitHub REST adapter. Fixed host, no redirects, bounded acquisition.

Never reads local git credentials. The operator supplies a workspace-specific
environment reference. No issue text can grant permissions or launch a process.
"""
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .model import Fault, require


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_repository(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value)
            and all(x not in {'.', '..'} for x in value.split('/')),
            'invalid_input', 'Use a GitHub repository in owner/repository form')
    return value


def credential(reference):
    if not reference:
        return ''
    require(re.fullmatch(r'GANTRY_CONNECTOR_[A-Z0-9_]+', reference), 'invalid_input',
            'Credential references must start with GANTRY_CONNECTOR_')
    token = os.environ.get(reference, '')
    require(bool(token), 'credential_missing', 'The operator has not configured this credential reference')
    require('\n' not in token and '\r' not in token, 'credential_missing', 'Invalid credential configuration')
    return token


def fetch_repository(config):
    repo = validate_repository(config['repository'])
    token = credential(config.get('credential_ref'))
    opener = build_opener(NoRedirect())
    requests = 0
    deadline = time.monotonic() + 25
    def get(suffix):
        nonlocal requests
        requests += 1
        require(requests <= 24, 'acquisition_limit', 'GitHub request budget reached')
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'acquisition_limit', 'GitHub synchronization time budget reached')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Gantry/1.0',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        try:
            with opener.open(Request('https://api.github.com/repos/' + repo + suffix, headers=headers), timeout=min(8, remaining)) as r:
                raw = r.read(4 * 1024 * 1024 + 1)
                require(len(raw) <= 4 * 1024 * 1024, 'acquisition_limit', 'GitHub response exceeds acquisition limit')
                return json.loads(raw), bool(r.headers.get('Link', '').find('rel="next"') >= 0)
        except HTTPError as exc:
            # Remote bodies/headers can contain private data. Persist only a bounded classification.
            raise Fault('github_http_' + str(exc.code), 'GitHub returned HTTP ' + str(exc.code) +
                '; check repository access, permissions and rate limits') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise Fault('github_unavailable', 'GitHub could not be read; retry after checking connectivity') from None

    metadata, _ = get('')
    issues, next_page = get('/issues?state=all&sort=updated&direction=desc&per_page=50')
    require(isinstance(issues, list), 'github_invalid_response', 'Expected a GitHub issue list')
    signals = []
    for item in issues:
        number = item.get('number')
        require(isinstance(number, int) and number > 0, 'github_invalid_response', 'Invalid GitHub issue number')
        is_pr = 'pull_request' in item
        signal = {'source_event_id': str(number), 'kind': 'pull_request' if is_pr else 'issue',
            'title': str(item.get('title', 'Untitled'))[:500], 'body': str(item.get('body') or '')[:40000],
            'source_status': item.get('state', 'unknown'), 'occurred_at': str(item.get('updated_at', 'unknown')),
            'url': 'https://github.com/' + repo + ('/pull/' if is_pr else '/issues/') + str(number),
            'repository': repo, 'number': number, 'capture_missing': ['comments', 'earlier revisions'],
            'observed_configuration': {}, 'metrics': {}}
        if len(str(item.get('body') or '')) > 40000:
            signal['capture_missing'].append('body truncated after 40000 characters')
        # Enrich a bounded number of PRs; make incompleteness explicit, never infer CI success.
        if is_pr and sum(x['kind'] == 'pull_request' for x in signals) < 5:
            try:
                pr, _ = get('/pulls/' + str(number))
                sha = pr.get('head', {}).get('sha', '')
                require(re.fullmatch('[a-f0-9]{40}', sha), 'github_invalid_response', 'Invalid PR head SHA')
                files, more_files = get('/pulls/' + str(number) + '/files?per_page=100')
                signal.update(head_sha=sha, base_sha=pr.get('base', {}).get('sha'),
                    merged=bool(pr.get('merged')), draft=bool(pr.get('draft')),
                    files=[{k: f[k] for k in ('filename', 'status', 'additions', 'deletions', 'patch') if k in f}
                           for f in files if isinstance(f, dict)])
                if more_files: signal['capture_missing'].append('PR files after first 100')
                if any('patch' not in f for f in signal['files']): signal['capture_missing'].append('binary or unavailable patches')
                checks, more_checks = get('/commits/' + sha + '/check-runs?per_page=100')
                signal['checks'] = [{k: c[k] for k in ('name', 'status', 'conclusion', 'head_sha') if k in c}
                                    for c in checks.get('check_runs', [])]
                if more_checks: signal['capture_missing'].append('check runs after first 100')
                signal['capture_missing'].append('legacy commit statuses')
            except Fault as exc:
                signal['capture_missing'].append('PR enrichment: ' + exc.code)
            # File acquisition is not atomic with reading PR heads. Recheck even
            # if Checks access was denied; unverified patches must not be bound
            # to an earlier head/base pair.
            if 'files' in signal:
                try:
                    latest, _ = get('/pulls/' + str(number))
                    if latest.get('head', {}).get('sha') != signal['head_sha'] or latest.get('base', {}).get('sha') != signal['base_sha']:
                        signal.pop('files', None)
                        signal['capture_missing'].append('PR moved during acquisition; patches discarded, retry synchronization')
                except Fault as exc:
                    signal.pop('files', None)
                    signal['capture_missing'].append('PR version could not be rechecked; patches discarded: ' + exc.code)
        elif is_pr:
            signal['capture_missing'].append('PR details and checks outside per-sync budget')
        signals.append(signal)
    return {'signals': signals, 'repository_id': metadata.get('id'),
            'partial': next_page, 'coverage': '50 most recently updated issues/PRs; up to 5 PRs with files and check runs',
            'requests': requests}
