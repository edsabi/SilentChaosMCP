"""Silent Chaos MCP Server — Flask Blueprint.

Supports two MCP transports:

  Streamable HTTP (MCP 2025-03-26) — recommended for Claude Desktop:
    POST /mcp    — all JSON-RPC messages; session tracked via Mcp-Session-Id header
    DELETE /mcp  — terminate a session
    GET  /mcp    — server-initiated SSE (optional, returns 405 if not needed)

  Legacy HTTP+SSE (MCP 2024-11-05) — for older clients:
    GET  /mcp/sse                  — open SSE stream, receive session endpoint URL
    POST /mcp/messages?sessionId=X — send JSON-RPC messages for that session

  GET  /mcp/health               — liveness check

Environment:
  GAME_BASE_URL   URL the MCP clients use to reach the game API.
                  Defaults to http://localhost:5000 (loopback when embedded).
  MCP_API_KEY     If set, clients must send  Authorization: Bearer <key>
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue as _queue
import threading
import uuid
from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, abort, jsonify, request, stream_with_context

from client import GameClient
from protocol import error_response, ok_response, tool_result
from tools import TOOL_LIST, TOOL_REGISTRY

log = logging.getLogger(__name__)

GAME_BASE_URL: str = os.environ.get("GAME_BASE_URL", "http://localhost:5000")
MCP_API_KEY: Optional[str] = os.environ.get("MCP_API_KEY") or None

# Persist signed-up IPs across restarts
_SIGNUP_IP_FILE = Path(__file__).parent / "mcp_signup_ips.json"
_signup_ips: set[str] = set()
_signup_ips_lock = threading.Lock()


def _load_signup_ips() -> None:
    if _SIGNUP_IP_FILE.exists():
        try:
            data = json.loads(_SIGNUP_IP_FILE.read_text())
            _signup_ips.update(data)
        except Exception:
            pass


def _save_signup_ips() -> None:
    try:
        _SIGNUP_IP_FILE.write_text(json.dumps(list(_signup_ips)))
    except Exception as e:
        log.warning("Could not save signup IPs: %s", e)


_load_signup_ips()

import time as _time

mcp_bp = Blueprint("mcp", __name__, url_prefix="/mcp")

# Legacy SSE-transport sessions (2024-11-05)
# Sessions are kept alive for _SSE_LINGER_SECS after SSE disconnect so a quick
# reconnect can reuse the same GameClient (and its stored api_key).
_sessions: dict[str, "_Session"] = {}
_sessions_lock = threading.Lock()
_SSE_LINGER_SECS = 300  # 5-minute grace period after SSE disconnect

# Streamable HTTP sessions (2025-03-26) — persist independently of HTTP connections
_sh_sessions: dict[str, "_Session"] = {}
_sh_sessions_lock = threading.Lock()
_SH_SESSION_TTL = 3600  # seconds; idle sessions are pruned on access


def _client_ip() -> str:
    """Return the real client IP, honouring nginx's X-Real-IP header."""
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


class _Session:
    """One MCP client connection: dedicated event loop + GameClient + message queue."""

    def __init__(self, ip: str) -> None:
        self.sid = uuid.uuid4().hex
        self.ip = ip
        self.last_used = _time.monotonic()
        self.sse_disconnected_at: Optional[float] = None
        self.loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self.loop.run_forever, daemon=True, name=f"mcp-loop-{self.sid[:8]}"
        )
        self._loop_thread.start()
        self.client = GameClient(base_url=GAME_BASE_URL)
        self.queue: _queue.Queue = _queue.Queue()

    def run(self, coro, timeout: float = 30.0):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)

    def dispatch(self, msg: dict) -> Optional[dict]:
        method = msg.get("method", "")
        req_id = msg.get("id")

        if method == "initialize":
            # Negotiate protocol version: honour client's request if we support it
            client_proto = (msg.get("params") or {}).get("protocolVersion", "2024-11-05")
            proto = client_proto if client_proto in ("2024-11-05", "2025-03-26") else "2025-03-26"
            return ok_response(
                req_id,
                {
                    "protocolVersion": proto,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "silent-chaos", "version": "1.0.0"},
                },
            )

        if method in ("notifications/initialized", "notifications/cancelled"):
            return None

        if method == "tools/list":
            return ok_response(req_id, {"tools": TOOL_LIST})

        if method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            if name not in TOOL_REGISTRY:
                return error_response(req_id, -32601, f"Unknown tool: {name}")

            # One signup per IP via MCP
            if name == "signup":
                with _signup_ips_lock:
                    if self.ip in _signup_ips:
                        return ok_response(
                            req_id,
                            tool_result(json.dumps({
                                "ok": False,
                                "error": "An account has already been created from your IP address via MCP.",
                            })),
                        )

            try:
                result = self.run(TOOL_REGISTRY[name](self.client, args))
                # Record IP on successful signup
                if name == "signup" and result.get("ok"):
                    with _signup_ips_lock:
                        _signup_ips.add(self.ip)
                        _save_signup_ips()
                    log.info("MCP signup from %s recorded", self.ip)
                return ok_response(req_id, tool_result(json.dumps(result, indent=2)))
            except Exception as exc:
                return ok_response(
                    req_id,
                    tool_result(json.dumps({"ok": False, "error": str(exc)})),
                )

        if method == "ping":
            return ok_response(req_id, {})

        if req_id is not None:
            return error_response(req_id, -32601, f"Method not found: {method}")

        return None

    def close(self) -> None:
        self.queue.put(None)  # unblock any waiting generator
        self.loop.call_soon_threadsafe(self.loop.stop)


def _check_auth() -> None:
    if not MCP_API_KEY:
        return
    if request.headers.get("Authorization", "") != f"Bearer {MCP_API_KEY}":
        abort(401)


@mcp_bp.get("/sse")
def sse_connect():
    _check_auth()
    ip = _client_ip()
    session = _Session(ip=ip)
    with _sessions_lock:
        _sessions[session.sid] = session
    log.info("MCP session %s opened from %s (total=%d)", session.sid[:8], ip, len(_sessions))

    def generate():
        yield f"event: endpoint\ndata: /mcp/messages?sessionId={session.sid}\n\n"
        try:
            while True:
                try:
                    msg = session.queue.get(timeout=15.0)
                    if msg is None:
                        break
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                except _queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            # Mark disconnected but keep session alive so a quick reconnect
            # can reuse the same GameClient and its stored api_key.
            session.sse_disconnected_at = _time.monotonic()
            log.info("MCP SSE session %s disconnected — lingering for %ds", session.sid[:8], _SSE_LINGER_SECS)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _prune_sse_sessions() -> None:
    cutoff = _time.monotonic() - _SSE_LINGER_SECS
    with _sessions_lock:
        stale = [
            sid for sid, s in _sessions.items()
            if s.sse_disconnected_at is not None and s.sse_disconnected_at < cutoff
        ]
        for sid in stale:
            _sessions.pop(sid).close()
    if stale:
        log.info("pruned %d expired SSE sessions", len(stale))


@mcp_bp.post("/messages")
def post_message():
    _check_auth()
    _prune_sse_sessions()
    sid = request.args.get("sessionId", "")
    with _sessions_lock:
        session = _sessions.get(sid)
    if not session:
        abort(404)

    msg = request.get_json(force=True, silent=True)
    if msg is None:
        abort(400)

    # Reset linger timer — client is actively sending messages
    session.sse_disconnected_at = None
    session.last_used = _time.monotonic()

    response = session.dispatch(msg)
    if response is not None:
        session.queue.put(response)

    return "", 202


def _prune_sh_sessions() -> None:
    """Remove Streamable HTTP sessions idle longer than TTL."""
    cutoff = _time.monotonic() - _SH_SESSION_TTL
    with _sh_sessions_lock:
        stale = [sid for sid, s in _sh_sessions.items() if s.last_used < cutoff]
        for sid in stale:
            _sh_sessions.pop(sid).close()
    if stale:
        log.info("pruned %d idle Streamable HTTP sessions", len(stale))


@mcp_bp.route("/", methods=["POST", "GET", "DELETE"], strict_slashes=False)
def streamable_mcp():
    """MCP Streamable HTTP transport (2025-03-26).

    POST   /mcp  — send JSON-RPC message(s); Mcp-Session-Id header required after initialize
    DELETE /mcp  — terminate session
    GET    /mcp  — not supported (returns 405)
    """
    _check_auth()
    _prune_sh_sessions()

    if request.method == "DELETE":
        sid = request.headers.get("Mcp-Session-Id", "")
        with _sh_sessions_lock:
            session = _sh_sessions.pop(sid, None)
        if session:
            session.close()
            log.info("Streamable HTTP session %s terminated", sid[:8])
        return "", 200

    if request.method == "GET":
        return "", 405

    # POST
    body = request.get_json(force=True, silent=True)
    if body is None:
        return jsonify({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}), 400

    msgs = body if isinstance(body, list) else [body]
    session_id = request.headers.get("Mcp-Session-Id", "")
    responses = []
    active_session: Optional["_Session"] = None

    for m in msgs:
        method = m.get("method", "")
        req_id = m.get("id")
        is_notification = req_id is None

        if method == "initialize":
            ip = _client_ip()
            active_session = _Session(ip=ip)
            session_id = active_session.sid
            with _sh_sessions_lock:
                _sh_sessions[session_id] = active_session
            log.info("Streamable HTTP session %s opened from %s (total=%d)", session_id[:8], ip, len(_sh_sessions))
            resp = active_session.dispatch(m)
            if resp is not None:
                responses.append(resp)

        elif method in ("notifications/initialized", "notifications/cancelled"):
            pass  # fire-and-forget, no response

        else:
            if not session_id:
                if not is_notification:
                    responses.append({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": "Missing Mcp-Session-Id header"}})
                continue

            with _sh_sessions_lock:
                active_session = _sh_sessions.get(session_id)

            if active_session is None:
                if not is_notification:
                    responses.append({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32001, "message": "Session not found — please re-initialize"}})
                continue

            active_session.last_used = _time.monotonic()
            resp = active_session.dispatch(m)
            if resp is not None:
                responses.append(resp)

    if not responses:
        r = Response("", status=202)
        if session_id:
            r.headers["Mcp-Session-Id"] = session_id
        return r

    response_body = responses[0] if len(responses) == 1 else responses
    r = jsonify(response_body)
    if session_id:
        r.headers["Mcp-Session-Id"] = session_id
    return r


@mcp_bp.get("/health")
def health():
    with _signup_ips_lock:
        signup_count = len(_signup_ips)
    return jsonify({
        "ok": True,
        "sessions_legacy_sse": len(_sessions),
        "sessions_streamable_http": len(_sh_sessions),
        "mcp_signups": signup_count,
    })
