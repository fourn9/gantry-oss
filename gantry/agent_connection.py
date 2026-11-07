"""Portable local MCP configuration; no provider keys or host config mutation."""
import json
import os
from pathlib import Path
from .client import validate_url
from .model import require

READ_TOOLS = set('context reviews events project_details session_details product_overview identity get_development_state list_development_states development_state get_change_review list_change_reviews related_review_context get_review_team review_automation_status get_evidence_view query_evidence get_validation_plan state why impact open history outcomes design review_context list_artifact_files read_artifact_chunk read_artifact_batch restore_artifact'.split())
READ_TOOLS.add('render_evidence_view')
READ_TOOLS.add('get_design_assessment')
READ_TOOLS.update({'studio_library','studio_related','studio_context','studio_overview','studio_work','studio_inbox','studio_team','get_onboarding','list_onboardings'})
READ_TOOLS.update({'get_persistent_bot', 'list_persistent_memories', 'bot_inbox'})
DEVELOP_TOOLS = set('record capture_artifact begin_change checkpoint_change share_change integrate_changes submit_change_review respond_to_change_review create_work claim_work submit_work discuss'.split())
DEVELOP_TOOLS.update({'studio_comment','studio_acknowledge','studio_import_update','studio_share_update','studio_sync_update','record_state_restore'})
REVIEW_TOOLS = set('claim_change_review submit_specialist_review complete_change_review propose_review_work reflect_change_review claim_mentor_job check_mentor_job finish_mentor_job fail_mentor_job'.split())
REVIEW_TOOLS.add('recover_mentor_job')
READ_TOOLS.update({'get_bot_context', 'list_bot_memories', 'list_team_messages', 'get_team_proposal', 'get_crew_setup', 'list_crew_setups'})
TEAM_TOOLS = {'start_bot_runtime', 'heartbeat_bot_runtime', 'stop_bot_runtime', 'propose_review_team', 'send_team_message', 'resolve_team_message', 'record_bot_memory'}
DEVELOP_TOOLS.update({'propose_onboarding','propose_crew_setup'})
DEVELOP_TOOLS.update(TEAM_TOOLS | {'claim_mentor_job', 'check_mentor_job', 'finish_mentor_job', 'fail_mentor_job', 'recover_mentor_job'})
REVIEW_TOOLS.update(TEAM_TOOLS)
PROFILES = {'read-only': READ_TOOLS, 'developer': READ_TOOLS | DEVELOP_TOOLS,
            'reviewer': READ_TOOLS | REVIEW_TOOLS}
BOT_READS = set('identity events get_development_state list_development_states get_persistent_bot '
    'list_persistent_memories bot_inbox get_bot_project get_bot_task list_bot_tasks check_bot_task '
    'list_artifact_files read_artifact_chunk read_artifact_batch restore_artifact get_evidence_view query_evidence'.split())
BOT_WRITES = set('propose_bot_requirements integrate_bot_task capture_artifact assign_bot_task claim_bot_task checkpoint_bot_task finish_bot_task '
    'hold_bot_task recover_bot_task cancel_bot_task send_bot_message resolve_bot_message '
    'start_bot_runtime heartbeat_bot_runtime stop_bot_runtime record_state_restore'.split())
BOT_READS.add('list_bot_handoffs')
BOT_READS.add('get_bot_requirements')
BOT_WRITES.update({'request_bot_handoff','acknowledge_bot_handoff','accept_bot_handoff'})
PROFILES['bot'] = BOT_READS | BOT_WRITES | {'get_design_assessment','studio_library','studio_related','studio_context','studio_overview','studio_work','studio_inbox','studio_team','studio_comment','studio_acknowledge'}
PROFILES['bot'].update({'get_bot_working_state', 'update_bot_working_state', 'record_bot_learning_use', 'poll_bot_continuations'})
PROFILES['bot'].update({'get_bot_learning_plan', 'prepare_bot_learning', 'submit_bot_learning_plan', 'complete_empty_bot_learning', 'get_bot_reflection', 'list_bot_reflections', 'complete_bot_reflection'})
PROFILES['bot'].update({'refresh_bot_task', 'ask_bot', 'record_bot_decision', 'record_bot_action', 'record_bot_experience'})
PROFILES['bot'].update({'propose_bot_team', 'get_bot_team_proposal', 'get_bot_records'})
PROFILES['bot'].update({'resolve_bot_question', 'stop_bot_task'})
PROFILES['bot'].update({'get_crew_setup','list_crew_setups','propose_crew_setup'})
# Standalone review does not expose organizational setup or Bot execution.
PROFILES['review'] = (READ_TOOLS | REVIEW_TOOLS) - (TEAM_TOOLS | {
    'get_persistent_bot', 'list_persistent_memories', 'bot_inbox', 'get_bot_context',
    'list_bot_memories', 'list_team_messages', 'get_team_proposal', 'get_crew_setup', 'list_crew_setups'})


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
