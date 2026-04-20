#!/usr/bin/env python3
"""Silent Chaos MCP Server — HTTP+SSE transport (MCP spec 2024-11-05).

Each connecting client gets an isolated session with its own GameClient,
so multiple AIs can play simultaneously with independent auth state.

Endpoints:
  GET  /sse                  — open SSE stream, receive session endpoint URL
  POST /messages?sessionId=X — send JSON-RPC messages for that session
  GET  /health               — liveness check

Environment:
  GAME_BASE_URL   game server URL (default http://localhost:5000)
  MCP_HOST        bind host (default 0.0.0.0)
  MCP_PORT        bind port (default 8000)
  MCP_API_KEY     if set, clients must send  Authorization: Bearer <key>
"""

import asyncio
import json
import logging
import os
import uuid
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from client import GameClient
from protocol import error_response, ok_response, tool_result
from tools import TOOL_LIST, TOOL_REGISTRY

logging.basicConfig(level=logging.INFO, format="[silent-chaos] %(message)s")
log = logging.getLogger(__name__)

GAME_BASE_URL = os.environ.get("GAME_BASE_URL", "http://localhost:5000")
MCP_API_KEY = os.environ.get("MCP_API_KEY") or None

app = FastAPI(title="Silent Chaos MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> {"client": GameClient, "queue": asyncio.Queue}
_sessions: dict[str, dict] = {}


def _check_auth(request: Request) -> None:
    if not MCP_API_KEY:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {MCP_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _make_session() -> tuple[str, dict]:
    sid = uuid.uuid4().hex
    client = GameClient(base_url=GAME_BASE_URL)
    queue: asyncio.Queue = asyncio.Queue()
    session = {"client": client, "queue": queue}
    _sessions[sid] = session
    log.info("new session %s (total=%d)", sid[:8], len(_sessions))
    return sid, session


async def _dispatch(session: dict, msg: dict) -> dict:
    client: GameClient = session["client"]
    method = msg.get("method", "")
    req_id = msg.get("id")

    if method == "initialize":
        return ok_response(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "silent-chaos", "version": "1.0.0"},
            },
        )

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None  # no response for notifications

    if method == "tools/list":
        return ok_response(req_id, {"tools": TOOL_LIST})

    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name", "")
        args = params.get("arguments", {})
        if name not in TOOL_REGISTRY:
            return error_response(req_id, -32601, f"Unknown tool: {name}")
        try:
            result = await TOOL_REGISTRY[name](client, args)
            return ok_response(req_id, tool_result(json.dumps(result, indent=2)))
        except Exception as exc:
            return ok_response(
                req_id, tool_result(json.dumps({"ok": False, "error": str(exc)}))
            )

    if method == "ping":
        return ok_response(req_id, {})

    if req_id is not None:
        return error_response(req_id, -32601, f"Method not found: {method}")

    return None


@app.get("/health")
async def health():
    return {"ok": True, "sessions": len(_sessions)}


@app.get("/sse")
async def sse_connect(request: Request):
    _check_auth(request)
    sid, session = _make_session()

    async def event_stream() -> AsyncIterator[str]:
        # Tell the client where to POST messages
        endpoint = f"/messages?sessionId={sid}"
        yield f"event: endpoint\ndata: {endpoint}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(session["queue"].get(), timeout=15.0)
                    payload = json.dumps(msg)
                    yield f"event: message\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _sessions.pop(sid, None)
            log.info("session %s closed (total=%d)", sid[:8], len(_sessions))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/messages")
async def post_message(request: Request, sessionId: str):
    _check_auth(request)

    session = _sessions.get(sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        msg = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    response = await _dispatch(session, msg)
    if response is not None:
        await session["queue"].put(response)

    return Response(status_code=202)


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    log.info("starting on %s:%d  game=%s  auth=%s", host, port, GAME_BASE_URL, bool(MCP_API_KEY))
    uvicorn.run(app, host=host, port=port)
