"""Newline-delimited MCP JSON-RPC over stdio; no local database bypass."""
import json
import sys
from . import __version__
from .model import Fault, canonical
from .service import Service
from .contracts import CONTRACTS
from .agent_connection import PROFILES


def tool_list(profile=None):
    names = sorted(name[4:] for name in dir(Service) if name.startswith("cmd_"))
    return [{"name": name, "description": CONTRACTS[name]["description"],
             "inputSchema": {"type": "object", "properties": {
                 "arguments": CONTRACTS[name]["schema"], "idempotency_key": {"type": "string", "minLength": 1}},
                 "required": ["arguments"] + ([] if name in Service.READS else ["idempotency_key"]), "additionalProperties": False},
             "annotations": {"readOnlyHint": name in Service.READS,
                             "destructiveHint": name not in Service.READS}}
            for name in names if profile is None or name in PROFILES[profile]]


def run(client, profile='read-only', require_agent=False):
    if require_agent:
        identity = client.call('identity')
        if identity.get('kind') != 'agent' or 'admin' in identity.get('permissions', []):
            raise Fault('unauthorized', 'Use a dedicated non-admin agent credential, not a human token')
    initialized = False
    while True:
        line = sys.stdin.readline(8 * 1024 * 1024 + 1)
        if not line: break
        if len(line) > 8 * 1024 * 1024:
            print(canonical({'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Message exceeds 8 MiB'}}), flush=True)
            return
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                raise ValueError("Invalid JSON-RPC request")
            method, params = request.get("method"), request.get("params", {})
            if not isinstance(params, dict): raise ValueError('params must be an object')
            if "id" not in request:
                if method == "notifications/initialized": initialized = True
                continue
            if method == "initialize":
                version = params.get("protocolVersion")
                result = {"protocolVersion": version if version in {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"} else "2025-11-25",
                          "capabilities": {"tools": {}}, "serverInfo": {"name": "gantry", "version": __version__}}
            elif method == "ping": result = {}
            elif not initialized: raise Fault("invalid_state", "Initialize first")
            elif method == "tools/list": result = {"tools": tool_list(profile)}
            elif method == "tools/call":
                name = params.get("name")
                if name not in {t["name"] for t in tool_list(profile)}: raise Fault("unknown_command", "Tool not exposed by this profile")
                data = params.get("arguments", {})
                if not isinstance(data, dict): raise ValueError('arguments must be an object')
                if name not in Service.READS and not data.get("idempotency_key"):
                    raise Fault("invalid_input", "Writes require a stable idempotency_key")
                try:
                    out = client.call(name, data.get("arguments", {}), data.get("idempotency_key"))
                    result = {"content": [{"type": "text", "text": canonical(out)}], "isError": False}
                except Fault as exc:
                    result = {"content": [{"type": "text", "text": canonical(exc.as_dict())}], "isError": True}
            else:
                print(canonical({"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "Method not found"}}), flush=True)
                continue
            response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except (ValueError, TypeError, Fault, OSError) as exc:
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                        "error": {"code": -32602 if isinstance(exc, Fault) else -32700, "message": str(exc)}}
        print(canonical(response), flush=True)
