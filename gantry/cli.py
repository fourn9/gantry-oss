"""Use python -m gantry. CLI commands go through the same HTTP authorization as MCP."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

from .client import Client
from .model import Fault
from .service import Service, token_hash


def main():
    parser = argparse.ArgumentParser(description="Gantry robot design ledger")
    parser.add_argument("--url", default=os.getenv("GANTRY_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--token-file", default=os.getenv("GANTRY_TOKEN_FILE"))
    sub = parser.add_subparsers(dest="command", required=True)
    connect = sub.add_parser('connect', help='Discover a local project and approve one scoped agent connection')
    connect.add_argument('root', nargs='?', default='.')
    connect.add_argument('--mode', choices=['record-only', 'work-capable'], default='work-capable')
    connect.add_argument('--client', choices=['claude', 'codex', 'cursor', 'generic'], default='generic')
    connect.add_argument('--path', action='append', help='Relative file or directory/ scope; default is discovered files only')
    connect.add_argument('--write-path', action='append', help='Writable subset of --path; use to keep acceptance tests read-only')
    connect.add_argument('--test-command', action='append', help='NAME=JSON_ARGV; explicitly replaces detected commands')
    connect.add_argument('--ttl', type=int, default=3600, help='Capability lifetime in seconds, at most eight hours')
    connect.add_argument('--prepare', action='store_true', help='Only save and display a plan; no token activated')
    connect.add_argument('--approve', help='Exact plan hash, for an owner who already reviewed a prepared plan')
    connect.add_argument('--goal', help='Delegated development goal')
    connect.add_argument('--done', action='append', help='Completion condition; repeat as needed')
    connect.add_argument('--constraint', action='append', help='Fixed constraint')
    connect.add_argument('--hold', action='append', help='Hold condition requiring owner decision')
    connect.add_argument('--mentor', choices=['client', 'codex-subscription'], default='client')
    disconnect = sub.add_parser('disconnect', help='Revoke this project connection; preserve audit history')
    disconnect.add_argument('root', nargs='?', default='.')
    project = sub.add_parser('project', help='Use scoped project operations with the agent credential')
    project.add_argument('action', choices=['status', 'read', 'edit', 'test', 'checkpoint', 'audit',
        'submit', 'review', 'respond', 'assumption', 'branch', 'mentor-prepare', 'mentor-finish', 'mentor-run'])
    project.add_argument('--root', default='.')
    project.add_argument('--input', help='JSON arguments file; - reads stdin')
    project.add_argument('--request-id', help='Stable ID for safe retries')
    project_mcp = sub.add_parser('project-mcp', help='Serve only the scoped local project tools over stdio')
    project_mcp.add_argument('--root', required=True)
    init = sub.add_parser("init", help="Local, one-time initialization")
    init.add_argument("--data", default=".gantry")
    init.add_argument("--actor", default="admin")
    init.add_argument("--feedback", choices=["off","statistics","diagnostics"], help="Explicit optional feedback choice; noninteractive default is off")
    init.add_argument("--consent-seconds", type=int, help="Explicit multi-zone consent period; unset blocks multi-zone review")
    serve = sub.add_parser("serve", help="Start authenticated HTTP API")
    serve.add_argument("--data", default=".gantry")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    cloud = sub.add_parser('serve-cloud', help='Serve separately provisioned cloud workspaces; run behind TLS')
    cloud.add_argument('--root', required=True)
    cloud.add_argument('--host', default='127.0.0.1')
    cloud.add_argument('--port', type=int, default=8765)
    call = sub.add_parser("call", help="Call an API operation")
    call.add_argument("operation")
    call.add_argument("--input", default="-", help="JSON file; '-' reads stdin")
    call.add_argument("--key", help="Reuse this key when retrying a write")
    mcp = sub.add_parser("mcp", help="Serve MCP over stdio; connects to HTTP API")
    from .agent_connection import PROFILES
    mcp.add_argument('--profile', choices=sorted(PROFILES), default='read-only')
    mcp.add_argument('--require-agent', action='store_true', help='Reject human/admin credentials')
    config = sub.add_parser('agent-config', help='Generate a portable MCP config without editing client settings')
    config.add_argument('--client', choices=['claude','cursor','codex','generic'], required=True)
    config.add_argument('--profile', choices=sorted(PROFILES), default='read-only')
    config.add_argument('--agent-token-file', required=True)
    config.add_argument('--executable', required=True, help='Absolute path to installed gantry executable')
    config.add_argument('--output', required=True)
    request = sub.add_parser('agent-request', help='Create a dedicated token and an unsigned principal proposal for owner review')
    request.add_argument('--name', required=True)
    request.add_argument('--profile', choices=sorted(PROFILES), required=True)
    request.add_argument('--zone', default='root')
    request.add_argument('--expires-days', type=int, default=30)
    request.add_argument('--output-token', required=True)
    request.add_argument('--output-proposal', required=True)
    usage = sub.add_parser('usage', help='Opt-in local statistics; never automatically sent')
    usage.add_argument('action', choices=['enable','disable','status','export','summarize'])
    usage.add_argument('--data', default='.gantry')
    usage.add_argument('--output')
    usage.add_argument('--input', nargs='+')
    cred = sub.add_parser("credential", help="Generate a local token and its public hash for a principal proposal")
    cred.add_argument("--output", required=True)
    restore = sub.add_parser("restore-backup", help="Offline import to an empty ledger")
    restore.add_argument("--data", required=True); restore.add_argument("--input", required=True)
    export = sub.add_parser("export", help="Export verified events and artifacts")
    export.add_argument("--output", required=True)
    artifact = sub.add_parser("restore-artifact")
    artifact.add_argument("revision_id"); artifact.add_argument("--destination", required=True)
    git = sub.add_parser("capture-git")
    git.add_argument("--repository", required=True); git.add_argument("--work-id", required=True)
    git.add_argument("--zone", default="root"); git.add_argument("--base")
    watch = sub.add_parser("watch-files", help="Record saved CAD/code files; no editor automation")
    watch.add_argument("--root", required=True); watch.add_argument("--files", nargs="+", required=True)
    watch.add_argument("--work-id", required=True); watch.add_argument("--zone", default="root")
    watch.add_argument("--journal", required=True); watch.add_argument("--once", action="store_true")
    worker = sub.add_parser("development-worker", help="One milestone/contract scheduling iteration")
    worker.add_argument("--session-id", required=True)
    worker.add_argument("--config", required=True, help="JSON with recipes and optional mentor provider argv")
    worker.add_argument("--journal", required=True)
    worker.add_argument("--contract-id", help="Run or resume a specific saved contract")
    worker.add_argument("--confirm-stopped", help="Reconcile an uncertain --contract-id after confirming the process stopped; provide reason")
    product_worker = sub.add_parser('product-worker', help='Outbound cloud Mentor, GitHub sync or customer-PC runner')
    product_worker.add_argument('--kind', choices=['mentor', 'runner', 'sync'], required=True)
    product_worker.add_argument('--config', required=True)
    product_worker.add_argument('--journal', required=True)
    product_worker.add_argument('--iterations', type=int, default=1)
    product_worker.add_argument('--interval', type=int, default=30)
    product_worker.add_argument('--worker-id')
    review = sub.add_parser('prepare-change-review', help='Claim a submitted PR and export Core context; no model invocation')
    review.add_argument('--submission-id', required=True)
    review.add_argument('--journal', required=True)
    finish_review = sub.add_parser('finish-change-review', help='Save the structured Mentor answer for a prepared PR')
    finish_review.add_argument('--journal', required=True)
    finish_review.add_argument('--input', required=True)
    mentor_daemon = sub.add_parser('mentor-worker', help='PR-triggered team worker using official Codex ChatGPT login')
    mentor_daemon.add_argument('--config', required=True)
    mentor_daemon.add_argument('--journal', required=True)
    mentor_daemon.add_argument('--iterations', type=int, default=1)
    mentor_daemon.add_argument('--interval', type=int, default=10)
    analyst = sub.add_parser('autonomy-worker', help='Continuously analyze Incoming and development milestones')
    analyst.add_argument('--config', required=True)
    analyst.add_argument('--journal', required=True)
    analyst.add_argument('--worker-id', required=True)
    analyst.add_argument('--iterations', type=int, default=0, help='0 runs until SIGTERM')
    analyst.add_argument('--interval', type=int, default=15)
    observe = sub.add_parser("observe-development", help="Import a completed external trial; mark intermediate history missing")
    observe.add_argument("--session-id", required=True)
    observe.add_argument("--root", required=True)
    observe.add_argument("--journal", required=True)
    observe.add_argument("--hypothesis", required=True)
    observe.add_argument("--rationale", required=True)
    observe.add_argument("--summary", required=True)
    observe.add_argument("--exit-code", type=int, required=True)
    capture = sub.add_parser('capture-workspace', help='Capture a saved workspace, excluding common credential files')
    capture.add_argument('--root', required=True); capture.add_argument('--key', required=True)
    capture.add_argument('--zone', default='root')
    checkpoint = sub.add_parser('checkpoint-workspace', help='Automatically save a change checkpoint')
    checkpoint.add_argument('--change-id', required=True); checkpoint.add_argument('--version', type=int, required=True)
    checkpoint.add_argument('--root', required=True); checkpoint.add_argument('--key', required=True)
    checkpoint.add_argument('--summary', required=True); checkpoint.add_argument('--rationale', required=True)
    checkpoint.add_argument('--unfinished', action='append', default=[])
    checkpoint.add_argument('--engineering-review', help='Carry Mentor-inferred roles/checks from this completed review')
    checkpoint.add_argument('--status', choices=['working', 'paused', 'completed', 'failed'], default='working')
    resume = sub.add_parser('restore-development-state', help='Restore saved bytes and continuation context into a new bundle')
    resume.add_argument('state_id'); resume.add_argument('--destination', required=True); resume.add_argument('--key', required=True)
    from .feedback import add_parser as feedback_parser
    feedback_parser(sub)
    args = parser.parse_args()
    try:
        if args.command == 'connect':
            from .project_connect import connect as connect_project
            commands = None
            if args.test_command:
                commands = {}
                for value in args.test_command:
                    name, raw = value.split('=', 1)
                    commands[name] = {'argv': json.loads(raw), 'timeout_seconds': 60}
            def confirm(preview):
                print(json.dumps(preview, indent=2), file=sys.stderr)
                if not sys.stdin.isatty(): return False
                print('Approve this connection? [y/N] ', end='', file=sys.stderr, flush=True)
                return sys.stdin.readline().strip().lower() == 'y'
            delegation = None
            if args.goal or args.done or args.constraint or args.hold or args.mentor != 'client':
                from .model import require
                require(args.goal and args.done, 'invalid_input', 'Provide --goal and at least one --done')
                delegation = {'goal': args.goal, 'done': args.done,
                    'constraints': args.constraint or ['No changed requirements or hardware operation'],
                    'hold': args.hold or ['An owner-only decision is necessary'], 'max_reviews': 3,
                    'max_tests': 10, 'max_branches': 3, 'mentor': args.mentor}
            result = connect_project(args.root, mode=args.mode, paths=args.path, commands=commands,
                client=args.client, ttl=args.ttl, prepare=args.prepare, approval=args.approve, confirm=confirm,
                delegation=delegation, write_paths=args.write_path)
        elif args.command == 'disconnect':
            from .project_connect import disconnect as disconnect_project
            result = disconnect_project(args.root)
        elif args.command == 'project-mcp':
            from .project_mcp import run as project_run
            project_run(args.root); return
        elif args.command == 'project':
            from .project_connect import Project, owner_client
            project = Project(args.root)
            if args.action == 'audit':
                result = owner_client(project.meta).call('inspect_connection', {'connection_id': project.receipt['connection_id']})
                result['history'] = owner_client(project.meta).call('history', {'limit': 500})
            else:
                payload = json.loads(sys.stdin.read() if args.input == '-' else Path(args.input).read_text()) if args.input else {}
                from .project_mcp import dispatch
                if args.action not in {'status', 'review', 'mentor-prepare', 'mentor-finish', 'mentor-run'}:
                    payload['request_id'] = args.request_id or payload.get('request_id') or secrets.token_hex(16)
                result = dispatch(project, 'project_'+args.action.replace('-', '_'), payload)
        elif args.command == 'feedback':
            from .feedback import command
            result = command(args)
        elif args.command == 'agent-config':
            from .agent_connection import connection_config
            raw = connection_config(args.client,args.url,args.agent_token_file,args.profile,args.executable)
            with open(args.output,'x') as f:
                os.chmod(args.output,0o600); f.write(raw)
            result={'config':str(Path(args.output).absolute()),'credentials_embedded':False,'client_settings_modified':False}
        elif args.command == 'agent-request':
            import time
            from .model import identifier, require
            identifier(args.name); identifier(args.zone)
            require(1 <= args.expires_days <= 365,'invalid_input','Expiry must be 1–365 days')
            require(not Path(args.output_token).exists() and not Path(args.output_proposal).exists(), 'conflict','Use new output paths')
            token=secrets.token_urlsafe(32)
            permissions=['read'] if args.profile=='read-only' else ['read','record','propose','work'] if args.profile=='developer' else ['read','propose']
            proposal={'title':'Delegate '+args.name,'changes':[{'id':args.name,'type':'principal','zone':args.zone,'data':{
                'kind':'agent','permissions':permissions,'zones':[args.zone], 'token_hash':token_hash(token),
                'allowed_commands':sorted(PROFILES[args.profile]),'expires_at':int(time.time()*1000)+args.expires_days*86400000}}]}
            for name,content in [(args.output_token,token+'\n'),(args.output_proposal,json.dumps(proposal,indent=2)+'\n')]:
                with open(name,'x') as f: os.chmod(name,0o600); f.write(content)
            result={'token_file':str(Path(args.output_token).absolute()),'proposal_file':str(Path(args.output_proposal).absolute()),
                    'active':False,'next':'Owner submits, reviews and commits the principal proposal; then delegates project/session participation.'}
        elif args.command == 'usage':
            from .usage_metrics import UsageMetrics,summarize
            metrics=UsageMetrics(args.data)
            if args.action in {'enable','disable'}: result=metrics.configure(args.action=='enable')
            elif args.action=='status': result={'local_collection':metrics.enabled(),'automatic_transmission':False}
            elif args.action=='summarize':
                if not args.input: raise Fault('invalid_input','Provide aggregate reports with --input')
                result=summarize([json.loads(Path(p).read_text()) for p in args.input])
            else:
                if not args.output: raise Fault('invalid_input','Choose a preview file with --output')
                with open(args.output,'x') as f:
                    os.chmod(args.output,0o600); json.dump(metrics.report(),f,indent=2)
                result={'preview_file':str(Path(args.output).absolute()),'sent':False,
                        'next':'Inspect this report and share voluntarily through your chosen channel.'}
        elif args.command == "init":
            result = Service(args.data).bootstrap(args.actor, args.consent_seconds)
            path = Path(args.data).resolve() / "admin.token"
            with open(path, "x") as f:
                os.chmod(path, 0o600); f.write(result.pop("token") + "\n")
            result["token_file"] = str(path)
            from .feedback import onboarding
            result["feedback"] = onboarding(args.data,args.feedback)
        elif args.command == "serve":
            from .server import serve
            serve(args.data, args.host, args.port); return
        elif args.command == 'serve-cloud':
            from .server import serve_cloud
            serve_cloud(args.root, args.host, args.port); return
        elif args.command == "credential":
            token = secrets.token_urlsafe(32)
            with open(args.output, "x") as f:
                os.chmod(args.output, 0o600); f.write(token + "\n")
            result = {"token_hash": token_hash(token), "token_file": str(Path(args.output).resolve())}
        elif args.command == "restore-backup":
            from .backup import restore_backup
            result = restore_backup(args.data, json.loads(Path(args.input).read_text()))
        else:
            token = Path(args.token_file).read_text().strip() if args.token_file else os.getenv("GANTRY_TOKEN", "")
            client = Client(args.url, token)
            if args.command == "mcp":
                from .mcp import run
                run(client,args.profile,args.require_agent); return
            if args.command == 'prepare-change-review':
                from .review_worker import prepare_review
                result = prepare_review(client, args.submission_id, args.journal)
                print(json.dumps(result['context'], ensure_ascii=False, indent=2)); return
            if args.command == 'finish-change-review':
                from .review_worker import finish_review
                result = finish_review(client, args.journal, json.loads(Path(args.input).read_text()))
                print(json.dumps(result, ensure_ascii=False, indent=2)); return
            if args.command == 'mentor-worker':
                from .mentor_daemon import run_mentor
                run_mentor(json.loads(Path(args.config).read_text()), args.journal, args.iterations, args.interval); return
            if args.command == 'autonomy-worker':
                from .autonomy_worker import run_analyst
                run_analyst(client, json.loads(Path(args.config).read_text()), args.journal,
                            args.worker_id, args.iterations, args.interval)
                return
            if args.command == 'product-worker':
                from .product_worker import run_worker
                run_worker(client, args.kind, json.loads(Path(args.config).read_text()), args.journal,
                           args.iterations, args.interval, args.worker_id)
                return
            if args.command == 'capture-workspace':
                from .continuity_adapter import capture_workspace
                artifact, missing = capture_workspace(client, args.root, args.key, args.zone)
                result = {'artifact': artifact, 'missing': missing}
            elif args.command == 'checkpoint-workspace':
                from .continuity_adapter import checkpoint_workspace
                result = checkpoint_workspace(client, args.change_id, args.version, args.root,
                    args.summary, args.rationale, args.unfinished, args.status, args.key, args.engineering_review)
            elif args.command == 'restore-development-state':
                from .continuity_adapter import restore_development_state
                result = restore_development_state(client, args.state_id, args.destination, args.key)
            elif args.command == "development-worker":
                from .runner import tick, run_contract, recover_run
                config = json.loads(Path(args.config).read_text())
                if args.confirm_stopped:
                    if not args.contract_id: raise Fault("invalid_input", "--confirm-stopped requires --contract-id")
                    result = recover_run(client, args.contract_id, config.get("recipes", {}), Path(args.journal) / "runs", args.confirm_stopped)
                else:
                    result = (run_contract(client, args.contract_id, config.get("recipes", {}), Path(args.journal) / "runs")
                          if args.contract_id else tick(client, args.session_id, config.get("mentor"),
                                                        config.get("recipes", {}), args.journal))
            elif args.command == "observe-development":
                from .runner import observe_saved_development
                result = observe_saved_development(client, args.session_id, args.root, args.journal,
                    args.hypothesis, args.rationale, args.summary, args.exit_code)
            elif args.command == "export":
                result = client.call("export")
                with open(args.output, "x") as f:
                    os.chmod(args.output, 0o600); json.dump(result, f, ensure_ascii=False)
                result = {"backup_file": str(Path(args.output).resolve()), "checkpoint": result["checkpoint"]}
            elif args.command == "restore-artifact":
                from .adapters import restore_files
                result = restore_files(client, args.revision_id, args.destination)
            elif args.command == "capture-git":
                from .adapters import capture_git
                result = capture_git(client, args.repository, args.work_id, args.zone, args.base)
            elif args.command == "watch-files":
                from .adapters import watch_saved_files
                result = watch_saved_files(client, args.root, args.files, args.work_id, args.zone, args.journal, once=args.once)
            else:
                data = json.load(sys.stdin) if args.input == "-" else json.loads(Path(args.input).read_text())
                result = client.call(args.operation, data, args.key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (Fault, OSError, ValueError) as exc:
        print(json.dumps({"error": exc.as_dict() if isinstance(exc, Fault) else str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__": main()
