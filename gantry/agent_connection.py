"""Portable local MCP configuration; no provider keys or host config mutation."""
import json
import os
from pathlib import Path
from .client import validate_url
from .model import require

READ_TOOLS = set('context reviews events project_details session_details product_overview identity get_development_state list_development_states development_state get_change_review list_change_reviews related_review_context get_review_team review_automation_status get_evidence_view query_evidence get_validation_plan state why impact open history outcomes design review_context list_artifact_files read_artifact_chunk read_artifact_batch restore_artifact'.split())
DEVELOP_TOOLS = set('record capture_artifact begin_change checkpoint_change share_change integrate_changes submit_change_review respond_to_change_review create_work claim_work submit_work discuss'.split())
REVIEW_TOOLS = set('claim_change_review submit_specialist_review complete_change_review propose_review_work reflect_change_review claim_mentor_job check_mentor_job finish_mentor_job fail_mentor_job'.split())
PROFILES = {'read-only': READ_TOOLS, 'developer': READ_TOOLS | DEVELOP_TOOLS,
            'reviewer': READ_TOOLS | REVIEW_TOOLS}


def connection_config(client, url, token_file, profile, executable):
    require(client in {'claude', 'cursor', 'codex', 'generic'} and profile in PROFILES,
            'invalid_input', 'Unsupported client/profile')
    validate_url(url)
    token_path = Path(token_file).expanduser().absolute()
    require(token_path.is_file() and not token_path.is_symlink(), 'invalid_input', 'Use a regular agent token file')
    if os.name == 'posix':
        require(token_path.stat().st_mode & 0o077 == 0, 'unauthorized', 'Agent token file must be owner-only (chmod 600)')
    command = str(Path(executable).expanduser().resolve())
    require(Path(command).is_file(), 'invalid_input', 'Gantry executable not found')
    args = ['--url', url, '--token-file', str(token_path), 'mcp', '--profile', profile, '--require-agent']
    if client == 'codex':
        return '[mcp_servers.gantry]\ncommand = '+json.dumps(command)+'\nargs = '+json.dumps(args)+'\n'
    return json.dumps({'mcpServers': {'gantry': {'type': 'stdio', 'command': command, 'args': args}}}, indent=2)+'\n'
